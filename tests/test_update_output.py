import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from termia.update_installers import command
from termia.update_output import MAX_LINE_CHARS, OutputLines
from termia.update_service import UpdateError


class UpdateOutputTests(unittest.TestCase):
    def test_split_urls_controls_and_final_partial_line(self):
        output = []
        lines = OutputLines(output.append)
        lines.feed("\x1b[31mDownloading https://user:secret@")
        self.assertEqual(output, [])
        lines.feed("example.invalid/path?token=private\x1b[0m\rDone\x00")
        lines.finish()
        self.assertEqual("".join(output), "Downloading [URL]\nDone\n")

    def test_oversized_lines_are_omitted_without_exposing_their_tail(self):
        output = []
        lines = OutputLines(output.append)
        lines.feed("https://" + "x" * MAX_LINE_CHARS)
        self.assertLessEqual(len(lines.pending), MAX_LINE_CHARS)
        lines.feed("private-tail\nnext\n")
        self.assertEqual("".join(output), "[…]\nnext\n")

    def test_output_is_delivered_before_process_exits(self):
        delivered, exited = Event(), Event()
        output = []

        def receive(text):
            output.append(text)
            delivered.set()
            self.assertFalse(exited.is_set())

        def run():
            try:
                return command([sys.executable, "-c", "import time; print('ready', flush=True); time.sleep(1)"],
                               Event(), output=receive)
            finally:
                exited.set()

        with ThreadPoolExecutor(max_workers=1) as workers:
            worker = workers.submit(run)
            self.assertTrue(delivered.wait(3))
            self.assertFalse(exited.is_set())
            worker.result(timeout=5)
        self.assertEqual("".join(output), "ready\n")

    def test_stderr_is_visible_on_failure_but_not_in_error_message(self):
        output = []
        with self.assertRaisesRegex(UpdateError, "^update_install_failed$"):
            command([sys.executable, "-c", "import sys; print('apt failed', file=sys.stderr); sys.exit(1)"],
                    Event(), output=output.append)
        self.assertEqual("".join(output), "apt failed\n")

    def test_cancellation_stops_a_streaming_preparation(self):
        cancel = Event()

        def receive(_text):
            cancel.set()

        with self.assertRaisesRegex(UpdateError, "^update_cancelled$"):
            command([sys.executable, "-c", "import time; print('start', flush=True); time.sleep(60)"],
                    cancel, output=receive)

    def test_applying_is_not_interrupted_by_cancel_and_large_output_is_drained(self):
        cancel = Event()
        output = []

        def receive(text):
            cancel.set()
            output.append(text)

        command([sys.executable, "-c", "import sys; print('line\\n' * 30000); print('last', file=sys.stderr)"],
                cancel, applying=True, output=receive)
        self.assertTrue(cancel.is_set())
        self.assertIn("last\n", "".join(output))
