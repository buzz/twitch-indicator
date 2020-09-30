# pylint: disable=wrong-import-position
"""Main entry point."""

import gi

gi.require_version("AppIndicator3", "0.1")
gi.require_version("Notify", "0.7")
gi.require_version("Gtk", "3.0")

from twitch_indicator.indicator import Indicator


def main():
    """Create Indicator and run main()."""
    gui = Indicator()
    gui.main()
