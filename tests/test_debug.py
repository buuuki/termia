import tempfile
import unittest
import logging
import os
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

    def test_glib_diagnostics_use_the_debug_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "debug.log"
            with patch.object(debug, "DEBUG_LOG_FILE", log_path):
                debug.configure_debug_logging(True)
                result = debug._write_glib_log(
                    GLib.LogLevelFlags.LEVEL_DEBUG,
                    {"MESSAGE": "GTK diagnostic", "GLIB_DOMAIN": "Gtk"},
                    2,
                    None,
                )

            self.assertEqual(result, GLib.LogWriterOutput.HANDLED)
            self.assertIn("[Gtk] GTK diagnostic", log_path.read_text(encoding="utf-8"))

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
