import webbrowser
import subprocess
from urllib.request import HTTPError
from urllib.parse import urlparse, urlunparse

from gi.repository import AppIndicator3, GdkPixbuf, Gtk, GLib

from twitch_indicator.cached_profile_image import CachedProfileImage
from twitch_indicator.constants import TWITCH_WEB_URL
from twitch_indicator.util import format_viewer_count, get_data_filepath


class Indicator:
    """App indicator."""

    def __init__(self, app):
        self.first_fetch = True
        self.app = app
        self.app_indicator = AppIndicator3.Indicator.new(
            "Twitch indicator",
            get_data_filepath("twitch-indicator.svg"),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.app_indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        # Setup menu
        self.setup_menu()

    def setup_menu(self):
        """Setup menu."""
        self.menu = Gtk.Menu()

        self.menu_item_channels = Gtk.MenuItem(label="Live channels")
        self.menu_item_channels.set_sensitive(False)

        self.menu_item_settings = Gtk.MenuItem(label="Settings")
        self.menu_item_settings.connect("activate", self.on_settings)

        self.menu_item_quit = Gtk.MenuItem(label="Quit")
        self.menu_item_quit.connect("activate", self.on_quit)

        self.app_indicator.set_menu(self.menu)
        self.refresh_menu_items()

    def add_streams_menu(self, streams):
        """Adds streams list to menu."""
        settings = self.app.settings.get()

        streams_menu = Gtk.Menu()
        self.menu_item_channels.set_submenu(streams_menu)

        # Order streams by viewer count
        streams_ordered = sorted(streams, key=lambda k: -k["viewer_count"])

        if streams_ordered:
            self.menu_item_channels.set_label(f"Live channels ({len(streams)})")
            self.menu_item_channels.set_sensitive(True)

            # Selected channels to top
            if settings.get_boolean("show-selected-channels-on-top"):
                enabled_channels = []
                other_channels = []
                enabled_channel_ids = self.app.channel_chooser.enabled_channel_ids

                for stream in streams_ordered:
                    try:
                        if enabled_channel_ids[stream["user_id"]]:
                            enabled_channels.append(stream)
                        else:
                            other_channels.append(stream)
                    except KeyError:
                        other_channels.append(stream)

                self.create_channel_menu_items(enabled_channels, streams_menu, settings)
                streams_menu.append(Gtk.SeparatorMenuItem())
                self.create_channel_menu_items(other_channels, streams_menu, settings)

            else:
                self.create_channel_menu_items(streams_ordered, streams_menu, settings)

        else:
            # No live channels
            self.menu_item_channels.set_label("No live channels...")
            self.menu_item_channels.set_sensitive(False)

        self.refresh_menu_items()

    def create_channel_menu_items(self, streams, streams_menu, settings):
        """Create menu items from streams array."""
        for stream in streams:
            menu_entry = Gtk.ImageMenuItem()

            # Channel icon
            pixbuf = CachedProfileImage.new_from_cached(stream["user_id"])
            pixbuf.scale_simple(32, 32, GdkPixbuf.InterpType.BILINEAR)
            icon = Gtk.Image.new_from_pixbuf(pixbuf)
            menu_entry.set_image(icon)

            # Channel label
            label = Gtk.Label()
            markup = f"<b>{GLib.markup_escape_text(stream['user_name'])}</b>"
            if settings.get_boolean("show-game-playing") and stream["game_name"]:
                markup += f" • {GLib.markup_escape_text(stream['game_name'])}"
            if settings.get_boolean("show-viewer-count"):
                viewer_count = format_viewer_count(stream["viewer_count"])
                markup += f" (<small>{viewer_count}</small>)"

            label.set_markup(markup)
            label.set_halign(Gtk.Align.START)
            menu_entry.add(label)
            url_parts = urlparse(TWITCH_WEB_URL)
            url = urlunparse(url_parts._replace(path=stream["user_login"]))
            menu_entry.connect("activate", self.on_stream_menu, url)

            streams_menu.append(menu_entry)

    def abort_refresh(self, exception, message, description):
        """Updates menu with failure state message."""
        self.menu_item_channels.set_label(message)
        self.menu_item_channels.set_sensitive(False)
        self.refresh_menu_items()

        # Skip error notification on first fetch (internet might not be up)
        if not self.first_fetch:
            if isinstance(exception, HTTPError):
                description = f"{description} (Error code: {exception.code})"

            self.app.notifications.show(message, description, category="network.error")

        self.first_fetch = False

    def refresh_menu_items(self):
        """Refresh all menu by removing and re-adding menu items."""
        for menu_item in self.menu.get_children():
            self.menu.remove(menu_item)
        self.menu.append(self.menu_item_channels)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(self.menu_item_settings)
        self.menu.append(self.menu_item_quit)
        self.menu.show_all()

    # UI callbacks

    def on_quit(self, _):
        """Callback for quit menu item."""
        self.app.quit()

    def on_settings(self, _):
        """Callback for settings menu item."""
        self.app.show_settings()

    def on_stream_menu(self, _, url):
        """Callback for stream menu item."""
        browser = webbrowser.get().basename
        cmd = self.app.settings.get().get_string("open-command")
        formatted = cmd.format(url=url, browser=browser).split()
        subprocess.Popen(formatted)
