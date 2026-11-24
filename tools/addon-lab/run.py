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
plugin_root = Path(os.environ.get("TERMIA_PLUGINS_DIR") or
                   root.parents[2] / "termia-plugins").expanduser().resolve()
if "--without-addon" not in sys.argv and not (plugin_root / "diagnostics/plugin.json").is_file():
    raise SystemExit("Diagnostics sources missing; set TERMIA_PLUGINS_DIR to the plugins directory")
os.environ["TERMIA_PLUGINS_DIR"] = str(plugin_root)
os.environ["TERMIA_DISABLE_PLUGINS"] = "1" if "--without-addon" in sys.argv else "0"
if "--without-addon" in sys.argv:
    sys.argv.remove("--without-addon")
# Preserve choices from the original laboratory without replacing newer ones.
for source in (profile / "config").glob("*-addon.disabled"):
    destination = profile / "config" / "termia" / "plugins" / source.name
    if not destination.exists():
        data = source.read_bytes()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(data)

sys.path.insert(0, str(root.parents[1] / "src"))

from termia.app import main

if __name__ == "__main__":
    raise SystemExit(main())
