import webbrowser
import os
from urllib.request import HTTPError

from gi.repository import AppIndicator3
from gi.repository import GdkPixbuf, Gtk, GLib

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

        self.menu_item_check_now = Gtk.MenuItem(label="Check now")
        self.menu_item_check_now.connect("activate", self.on_check_now)

        self.menu_item_channels = Gtk.MenuItem(label="Live channels")
        self.menu_item_channels.set_sensitive(False)

        self.menu_item_settings = Gtk.MenuItem(label="Settings")
        self.menu_item_settings.connect("activate", self.on_settings)

        self.menu_item_quit = Gtk.MenuItem(label="Quit")
        self.menu_item_quit.connect("activate", self.on_quit)

        self.app_indicator.set_menu(self.menu)
        self.refresh_menu_items()

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

        streams_menu = Gtk.Menu()
        self.menu_item_channels.set_submenu(streams_menu)

        # Order streams by viewer count
        streams_ordered = sorted(streams, key=lambda k: -k["viewer_count"])

        if streams_ordered:
            self.menu_item_channels.set_label(f"Live channels ({len(streams)})")
            self.menu_item_channels.set_sensitive(True)
            for index, stream in enumerate(streams_ordered):
                menu_entry = Gtk.MenuItem()
                box = Gtk.Box(Gtk.Orientation.HORIZONTAL, 8)

                # Channel icon
                pixbuf = (
                    stream["pixbuf"]
                    .get_pixbuf()
                    .scale_simple(32, 32, GdkPixbuf.InterpType.BILINEAR)
                )
                icon = Gtk.Image.new_from_pixbuf(pixbuf)
                box.pack_start(icon, False, False, 0)

                # Channel label
                label_main = Gtk.Label()
                markup = f"<b>{GLib.markup_escape_text(stream['name'])}</b>"
                if settings.get_boolean("show-game-playing") and stream["game"]:
                    markup += f" • {GLib.markup_escape_text(stream['game'])}"
                label_main.set_markup(markup)
                label_main.set_halign(Gtk.Align.START)
                box.pack_start(label_main, True, True, 0)

                # Channel viewer count
                if settings.get_boolean("show-viewer-count"):
                    label_viewer_count = Gtk.Label()
                    viewer_count = format_viewer_count(stream["viewer_count"])
                    label_viewer_count.set_markup(f"<small>{viewer_count}</small>")
                    label_viewer_count.set_halign(Gtk.Align.END)
                    box.pack_start(label_viewer_count, False, False, 10)

                menu_entry.add(box)
                streams_menu.append(menu_entry)
                streams_menu.get_children()[index].connect(
                    "activate", self.on_stream_menu, stream["url"]
                )
        else:
            self.menu_item_channels.set_label("No live channels...")
            self.menu_item_channels.set_sensitive(False)

        for i in streams_menu.get_children():
            i.show()

        self.refresh_menu_items()

    def abort_refresh(self, exception, message, description):
        """Updates menu with failure state message."""
        self.menu_item_channels.set_label(message)
        self.menu_item_channels.set_sensitive(False)
        self.enable_check_now()
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
        self.menu.append(self.menu_item_check_now)
        self.menu.append(self.menu_item_channels)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(self.menu_item_settings)
        self.menu.append(self.menu_item_quit)
        self.menu.show_all()

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
        os.system(cmd.format(url=url, browser=browser))
