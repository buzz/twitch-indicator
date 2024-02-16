import gi

gi.require_version("AppIndicator3", "0.1")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")

from twitch_indicator.app import TwitchIndicatorApp  # noqa: E402


def main():
    """Create and run app."""
    app = TwitchIndicatorApp()
    app.run(sys.argv)
