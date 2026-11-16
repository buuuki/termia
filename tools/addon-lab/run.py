#!/usr/bin/env python3
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
profile = root / "profile"
os.environ["XDG_CONFIG_HOME"] = str(profile / "config")
os.environ["XDG_STATE_HOME"] = str(profile / "state")
os.environ["XDG_CACHE_HOME"] = str(profile / "cache")
os.environ["XDG_DATA_HOME"] = str(profile / "data")
os.environ["TERMIA_CONFIG_DIR"] = str(profile / "config" / "termia")
os.environ["TERMIA_STATE_DIR"] = str(profile / "state" / "termia")
os.environ["TERMIA_LAB_PLUGINS"] = "0" if "--without-addon" in sys.argv else "1"
if "--without-addon" in sys.argv:
    sys.argv.remove("--without-addon")
sys.path.insert(0, str(root / "termia" / "src"))

from termia.app import main

if __name__ == "__main__":
    raise SystemExit(main())
