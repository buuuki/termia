import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import termia.constants as constants


class TermiaPathOverrideTests(unittest.TestCase):
    def test_termia_path_overrides_do_not_require_xdg_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_dir = root / "config" / "termia"
            state_dir = root / "state"
            environment = {
                **os.environ,
                "TERMIA_CONFIG_DIR": str(config_dir),
                "TERMIA_STATE_DIR": str(state_dir),
            }
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from termia import constants; print('\\n'.join(map(str, (constants.CONFIG_DIR, constants.DATA_FILE, constants.NOTES_FILE, constants.SETTINGS_FILE, constants.INSTANCE_LOCK_FILE, constants.STATE_DIR, constants.STATISTICS_FILE, constants.SESSION_SNAPSHOT_FILE))))",
                ],
                check=True,
                capture_output=True,
                env=environment,
                text=True,
            )

            self.assertEqual(
                result.stdout.splitlines(),
                [
                    str(config_dir),
                    str(config_dir / "connections.json"),
                    str(config_dir / "notes.json"),
                    str(config_dir / "settings.json"),
                    str(config_dir / "instance.lock"),
                    str(state_dir),
                    str(state_dir / "termia" / "statistics.json"),
                    str(state_dir / "termia" / "last-session.json"),
                ],
            )
