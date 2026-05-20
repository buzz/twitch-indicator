import sys

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")

try:
    gi.require_version("StatusNotifier", "1.0")
except (ImportError, ValueError):
    print(
        "Error: StatusNotifier GI overlay not found. "
        "Install libappindicator-gtk3 or python-gi-overrides-statusnotifier.",
        file=sys.stderr,
    )
    sys.exit(1)

from twitch_indicator.app import TwitchIndicatorApp  # noqa: E402


def main() -> None:
    """Create and run app."""
    app = TwitchIndicatorApp()
    try:
        app.run(sys.argv)
    except KeyboardInterrupt:
        app.quit()


if __name__ == "__main__":
    main()
