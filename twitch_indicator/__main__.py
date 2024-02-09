# pylint: disable=wrong-import-position

import gi

gi.require_version("AppIndicator3", "0.1")
gi.require_version("Notify", "0.7")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from twitch_indicator.app import TwitchIndicatorApp


def main():
    """Create and run app."""
    app = TwitchIndicatorApp()
    app.run()
