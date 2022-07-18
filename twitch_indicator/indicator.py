import webbrowser
import subprocess
from urllib.request import HTTPError

from gi.repository import AppIndicator3
from gi.repository import Gtk, GLib

from twitch_indicator.util import format_viewer_count, get_data_filepath


class Indicator:
    """App indicator."""

    def __init__(self, app):
        self.first_fetch = True
        self.app = app
        self.app_indicator = AppIndicator3.Indicator.new(
            "twitch-indicator",
            get_data_filepath("twitch-indicator.svg"),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.app_indicator.set_title("Twitch Indicator")
        self.app_indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        # Setup menu
        self.setup_menu()

    def setup_menu(self):
        """Setup menu."""
        self.menu = Gtk.Menu()
        self.app_indicator.set_menu(self.menu)

        self.menu_item_check_now = Gtk.MenuItem(label="Check now")
        self.menu_item_check_now.connect("activate", self.on_check_now)

        menu_item_settings = Gtk.MenuItem(label="Settings")
        menu_item_settings.connect("activate", self.on_settings)

        menu_item_quit = Gtk.MenuItem(label="Quit")
        menu_item_quit.connect("activate", self.on_quit)

        self.stream_menu_items = []

        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(self.menu_item_check_now)
        self.menu.append(menu_item_settings)
        self.menu.append(menu_item_quit)
        self.menu.show_all()

    def disable_check_now(self):
        """Disables check now button."""
        self.menu_item_check_now.set_sensitive(False)
        self.menu_item_check_now.set_label("Checking...")

    def enable_check_now(self):
        """Enables check now button."""
        self.menu_item_check_now.set_sensitive(True)
        self.menu_item_check_now.set_label("Check now")

    def add_streams_menu(self, streams):
        """Adds streams list to menu."""
        settings = self.app.settings.get()

        # Order streams by viewer count
        streams_ordered = sorted(streams, key=lambda k: -k["viewer_count"])

        for streamitem in self.stream_menu_items:
            self.menu.remove(streamitem)

        if streams_ordered:
            # Selected channels to top
            if settings.get_boolean("show-selected-channels-on-top"):
                enabled_channels = []
                other_channels = []
                enabled_channel_ids = self.app.channel_chooser.enabled_channel_ids

                for stream in streams_ordered:
                    try:
                        if enabled_channel_ids[stream["id"]]:
                            enabled_channels.append(stream)
                        else:
                            other_channels.append(stream)
                    except KeyError:
                        other_channels.append(stream)

                self.create_channel_menu_items(enabled_channels, self.menu, settings)
                sep = Gtk.SeparatorMenuItem()
                self.menu.prepend(sep)
                self.stream_menu_items.append(sep)
                self.create_channel_menu_items(other_channels, self.menu, settings)

            else:
                self.create_channel_menu_items(streams_ordered, self.menu, settings)

        else:
            menu_item_nolive = Gtk.MenuItem(label="No live channels...")
            menu_item_nolive.set_sensitive(False)
            self.stream_menu_items.append(menu_item_nolive)

        self.menu.show_all()

    def create_channel_menu_items(self, streams, streams_menu, settings):
        """Create menu items from streams array."""
        for stream in reversed(streams):
            menu_entry = Gtk.ImageMenuItem()

            # Channel icon
            pixbuf = stream["pixbuf"]
            icon = Gtk.Image.new_from_pixbuf(pixbuf)
            menu_entry.set_image(icon)

            # Channel label
            label = Gtk.Label()
            markup = f"<b>{GLib.markup_escape_text(stream['name'])}</b>"
            if settings.get_boolean("show-game-playing") and stream["game"]:
                markup += f" • {GLib.markup_escape_text(stream['game'])}"
            if settings.get_boolean("show-viewer-count"):
                viewer_count = format_viewer_count(stream["viewer_count"])
                markup += f" (<small>{viewer_count}</small>)"

            label.set_markup(markup)
            label.set_halign(Gtk.Align.START)
            menu_entry.add(label)
            menu_entry.connect("activate", self.on_stream_menu, stream["url"])

            self.stream_menu_items.append(menu_entry)
            streams_menu.prepend(menu_entry)

    def abort_refresh(self, exception, message, description):
        """Updates menu with failure state message."""
        self.menu_item_channels.set_label(message)
        self.menu_item_channels.set_sensitive(False)
        self.enable_check_now()

        # Skip error notification on first fetch (internet might not be up)
        if not self.first_fetch:
            if isinstance(exception, HTTPError):
                description = f"{description} (Error code: {exception.code})"

            self.app.notifications.show(message, description, category="network.error")

        self.first_fetch = False

    # UI callbacks

    def on_quit(self, _):
        """Callback for quit menu item."""
        self.app.quit()

    def on_check_now(self, _):
        """Callback for check now menu item."""
        self.app.start_api_thread()

    def on_settings(self, _):
        """Callback for settings menu item."""
        self.app.show_settings()

    def on_stream_menu(self, _, url):
        """Callback for stream menu item."""
        browser = webbrowser.get().basename
        cmd = self.app.settings.get().get_string("open-command")
        formated = cmd.format(url=url, browser=browser).split()
        subprocess.Popen(formated)
