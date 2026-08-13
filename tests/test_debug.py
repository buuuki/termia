import tempfile
import unittest
import logging
import os
import faulthandler
from pathlib import Path
from unittest.mock import patch

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

from termia import debug


class DebugLoggingTests(unittest.TestCase):
    def tearDown(self) -> None:
        debug.configure_debug_logging(False)

    def test_debug_logging_writes_to_file_without_stream_handler(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "debug.log"
            with patch.object(debug, "DEBUG_LOG_FILE", log_path):
                debug.configure_debug_logging(True)
                debug.LOGGER.info("file-only diagnostic")

            self.assertFalse(debug.LOGGER.propagate)
            self.assertTrue(log_path.read_text(encoding="utf-8").endswith("file-only diagnostic\n"))
            self.assertTrue(
                all(
                    not isinstance(handler, logging.StreamHandler)
                    or isinstance(handler, logging.FileHandler)
                    for handler in debug.LOGGER.handlers
                )
            )

    def test_glib_debug_noise_is_filtered_from_debug_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "debug.log"
            with patch.object(debug, "DEBUG_LOG_FILE", log_path):
                debug.configure_debug_logging(True)
                GLib.log_variant(
                    "GtkTest",
                    GLib.LogLevelFlags.LEVEL_DEBUG,
                    GLib.Variant(
                        "a{sv}",
                        {"MESSAGE": GLib.Variant("s", "GTK diagnostic")},
                    ),
                )

            contents = log_path.read_text(encoding="utf-8")
            self.assertNotIn("GtkTest", contents)
            self.assertNotIn("GTK diagnostic", contents)
            self.assertNotRegex(contents, r"DEBUG \[\d+\] \d+")

    def test_glib_warnings_remain_available_in_debug_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "debug.log"
            with patch.object(debug, "DEBUG_LOG_FILE", log_path):
                debug.configure_debug_logging(True)
                GLib.log_variant(
                    "GtkTest",
                    GLib.LogLevelFlags.LEVEL_WARNING,
                    GLib.Variant("a{sv}", {"MESSAGE": GLib.Variant("s", "Actionable warning")}),
                )

            contents = log_path.read_text(encoding="utf-8")
            self.assertIn("GtkTest", contents)
            self.assertIn("Actionable warning", contents)

    def test_application_events_are_structured_and_omit_none_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "debug.log"
            with patch.object(debug, "DEBUG_LOG_FILE", log_path):
                debug.configure_debug_logging(True)
                debug.log_event("split.created", session_id="session-1", pane_id=None, pane_count=3)

            contents = log_path.read_text(encoding="utf-8")
            self.assertIn("event=split.created pane_count=3 session_id=session-1", contents)
            self.assertNotIn("pane_id", contents)

    def test_faulthandler_writes_python_stack_to_debug_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "debug.log"
            with patch.object(debug, "DEBUG_LOG_FILE", log_path):
                debug.configure_debug_logging(True)
                self.assertTrue(faulthandler.is_enabled())
                handler = next(handler for handler in debug.LOGGER.handlers if isinstance(handler, logging.FileHandler))
                faulthandler.dump_traceback(file=handler.stream, all_threads=True)
                handler.flush()

            contents = log_path.read_text(encoding="utf-8")
            self.assertIn("Current thread", contents)
            self.assertIn("test_faulthandler_writes_python_stack_to_debug_file", contents)

    def test_debug_logging_does_not_enable_gsk_renderer_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "debug.log"
            with (
                patch.object(debug, "DEBUG_LOG_FILE", log_path),
                patch.dict(os.environ, {}, clear=True),
            ):
                debug.configure_debug_logging(True)

                self.assertNotIn("GSK_DEBUG", os.environ)

    def test_debug_logging_preserves_external_gsk_debug_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "debug.log"
            with (
                patch.object(debug, "DEBUG_LOG_FILE", log_path),
                patch.dict(os.environ, {"GSK_DEBUG": "shaders"}, clear=True),
            ):
                debug.configure_debug_logging(True)

                self.assertEqual(os.environ["GSK_DEBUG"], "shaders")
