"""Pin the laboratory panel without replacing existing GNOME favorites."""
from gi.repository import Gio

PANEL_ID = "org.termia.TestingLab.desktop"


def main():
    settings = Gio.Settings.new("org.gnome.shell")
    favorites = settings.get_strv("favorite-apps")
    if (PANEL_ID not in favorites
            and not settings.set_strv("favorite-apps", [*favorites, PANEL_ID])):
        raise RuntimeError("Could not pin the laboratory panel")
    Gio.Settings.sync()


if __name__ == "__main__":
    main()
