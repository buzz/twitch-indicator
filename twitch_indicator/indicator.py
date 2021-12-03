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

        self.menu_items = [
            Gtk.MenuItem(label="Check now"),
            Gtk.SeparatorMenuItem(),
            Gtk.MenuItem(label="Choose channels"),
            Gtk.MenuItem(label="Settings"),
            Gtk.MenuItem(label="Quit"),
        ]
        self.menu_items[0].connect("activate", self.on_check_now)
        self.menu_items[-3].connect("activate", self.on_channel_chooser)
        self.menu_items[-2].connect("activate", self.on_settings)
        self.menu_items[-1].connect("activate", self.on_quit)
        for i in self.menu_items:
            self.menu.append(i)

        self.app_indicator.set_menu(self.menu)
        self.menu.show_all()

    def disable_check_now(self):
        """Disables check now button."""
        self.menu.get_children()[0].set_sensitive(False)
        self.menu.get_children()[0].set_label("Checking...")

    def enable_check_now(self):
        """Enables check now button."""
        self.menu.get_children()[0].set_sensitive(True)
        self.menu.get_children()[0].set_label("Check now")

    def disable_channel_chooser(self):
        """Disables channel chooser button."""
        self.menu.get_children()[-3].set_sensitive(False)

    def enable_channel_chooser(self):
        """Enables channel chooser button."""
        self.menu.get_children()[-3].set_sensitive(True)

    def add_streams_menu(self, streams):
        """Adds streams list to menu."""
        settings = self.app.settings.get()

        # Remove live streams menu if already exists
        if len(self.menu_items) > 5:
            self.menu_items.pop(2)
            self.menu_items.pop(1)

        # Create menu
        streams_menu = Gtk.Menu()
        self.menu_items.insert(2, Gtk.MenuItem(label=f"Live channels ({len(streams)})"))
        self.menu_items.insert(3, Gtk.SeparatorMenuItem())
        self.menu_items[2].set_submenu(streams_menu)

        # Order streams by viewer count
        streams_ordered = sorted(streams, key=lambda k: -k["viewer_count"])

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
                box.pack_start(label_viewer_count, False, False, 10)

            menu_entry.add(box)
            streams_menu.append(menu_entry)
            streams_menu.get_children()[index].connect(
                "activate", self.on_stream_menu, stream["url"]
            )

        for i in streams_menu.get_children():
            i.show()

        # Refresh all menu by removing and re-adding menu items
        for i in self.menu.get_children():
            self.menu.remove(i)

        for i in self.menu_items:
            self.menu.append(i)

        self.menu.show_all()

    def abort_refresh(self, exception, message, description):
        """Updates menu with failure state message."""
        # Remove previous message if already exists
        if len(self.menu_items) > 4:
            self.menu_items.pop(2)
            self.menu_items.pop(1)

        self.menu_items.insert(2, Gtk.MenuItem(label=message))
        self.menu_items.insert(3, Gtk.SeparatorMenuItem())
        self.menu_items[2].set_sensitive(False)

        # Re-enable "Check now" button
        self.menu_items[0].set_sensitive(True)
        self.menu_items[0].set_label("Check now")

        # Refresh all menu items
        for i in self.menu.get_children():
            self.menu.remove(i)

        for i in self.menu_items:
            self.menu.append(i)

        self.menu.show_all()

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

    def on_channel_chooser(self, _):
        """Callback for channel chooser menu item."""
        self.app.show_channel_chooser()

    def on_settings(self, _):
        """Callback for settings menu item."""
        self.app.show_settings()

    def on_stream_menu(self, _, url):
        """Callback for stream menu item."""
        browser = webbrowser.get().basename
        cmd = self.app.settings.get().get_string("open-command")
        os.system(cmd.format(url=url, browser=browser))
