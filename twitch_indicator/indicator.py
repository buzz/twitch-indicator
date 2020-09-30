"""Desktop indicator"""

import threading
import webbrowser
from urllib.request import HTTPError

from gi.repository import AppIndicator3 as appindicator
from gi.repository import GLib, Gio, Notify
from gi.repository import Gtk

from twitch_indicator import get_data_filepath
from twitch_indicator.constants import SETTINGS_KEY
from twitch_indicator.twitch import TwitchApi


class Indicator:
    """App indicator."""

    live_streams = []
    user_id = None

    def __init__(self):
        self.thread = None
        self.timeout_thread = None
        self.twitch = None

        # Create applet
        self.app_indicator = appindicator.Indicator.new(
            "Twitch indicator",
            get_data_filepath("twitch-indicator.svg"),
            appindicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.app_indicator.set_status(appindicator.IndicatorStatus.ACTIVE)

        # Load settings
        self.settings = Gio.Settings.new(SETTINGS_KEY)

        # Setup menu
        self.menu = Gtk.Menu()
        self.menu_items = [
            Gtk.MenuItem(label="Check now"),
            Gtk.SeparatorMenuItem(),
            Gtk.MenuItem(label="Settings"),
            Gtk.MenuItem(label="Quit"),
        ]

        self.menu_items[0].connect("activate", self.refresh_streams_init, [True])
        self.menu_items[-2].connect("activate", self.settings_dialog)
        self.menu_items[-1].connect("activate", self.quit)

        for i in self.menu_items:
            self.menu.append(i)

        self.app_indicator.set_menu(self.menu)

        self.menu.show_all()

        self.refresh_streams_init(None)

    def clear_cache(self):
        """Clear cache."""
        self.user_id = None
        self.twitch.clear_cache()

    def open_link(self, _, url):
        """Opens link in default browser."""
        webbrowser.open_new_tab(url)

    def refresh_streams_init(self, _, button_activate=False):
        """"Refresh streams."""
        self.twitch = TwitchApi()

        # Initializes thread for stream refreshing.
        self.thread = threading.Thread(target=self.refresh_streams)
        self.thread.daemon = True
        self.thread.start()

        if button_activate is False:
            self.timeout_thread = threading.Timer(
                self.settings.get_int("refresh-interval") * 60,
                self.refresh_streams_init,
                [None],
            )
            self.timeout_thread.start()

    def settings_dialog(self, _):
        """Shows applet settings dialog."""
        dialog = Gtk.Dialog("Settings", None, 0)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        builder = Gtk.Builder()
        builder.add_from_file(get_data_filepath("twitch-indicator.glade"))

        builder.get_object("twitch_username").set_text(
            self.settings.get_string("twitch-username")
        )
        builder.get_object("show_notifications").set_active(
            self.settings.get_boolean("enable-notifications")
        )
        builder.get_object("show_game").set_active(
            self.settings.get_boolean("show-game-playing")
        )
        builder.get_object("refresh_interval").set_value(
            self.settings.get_int("refresh-interval")
        )

        box = dialog.get_content_area()
        box.add(builder.get_object("grid1"))
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            self.settings.set_string(
                "twitch-username", builder.get_object("twitch_username").get_text()
            )
            self.settings.set_boolean(
                "enable-notifications",
                builder.get_object("show_notifications").get_active(),
            )
            self.settings.set_boolean(
                "show-game-playing", builder.get_object("show_game").get_active()
            )
            self.settings.set_int(
                "refresh-interval",
                builder.get_object("refresh_interval").get_value_as_int(),
            )

            self.clear_cache()
        elif response == Gtk.ResponseType.CANCEL:
            pass

        dialog.destroy()

    def disable_menu(self):
        """Disables check now button."""
        self.menu.get_children()[0].set_sensitive(False)
        self.menu.get_children()[0].set_label("Checking...")

    def enable_menu(self):
        """Enables check now button."""
        self.menu.get_children()[0].set_sensitive(True)
        self.menu.get_children()[0].set_label("Check now")

    def add_streams_menu(self, streams):
        """Adds streams list to menu."""
        # Remove live streams menu if already exists
        if len(self.menu_items) > 4:
            self.menu_items.pop(2)
            self.menu_items.pop(1)

        # Create menu
        streams_menu = Gtk.Menu()
        self.menu_items.insert(2, Gtk.MenuItem(label=f"Live channels ({len(streams)})"))
        self.menu_items.insert(3, Gtk.SeparatorMenuItem())
        self.menu_items[2].set_submenu(streams_menu)

        # Order streams by alphabetical order
        streams_ordered = sorted(streams, key=lambda k: k["name"].lower())

        for index, stream in enumerate(streams_ordered):
            menu_entry = Gtk.MenuItem(label=f"{stream['name']} - {stream['game']}")
            streams_menu.append(menu_entry)
            streams_menu.get_children()[index].connect(
                "activate", self.open_link, stream["url"]
            )

        for i in streams_menu.get_children():
            i.show()

        # Refresh all menu by removing and re-adding menu items
        for i in self.menu.get_children():
            self.menu.remove(i)

        for i in self.menu_items:
            self.menu.append(i)

        self.menu.show_all()

    def refresh_streams(self):
        """Refreshes live streams list. Also pushes notifications when needed."""
        GLib.idle_add(self.disable_menu)

        if self.settings.get_string("twitch-username") == "":
            GLib.idle_add(
                self.abort_refresh,
                None,
                "Twitch username is not set",
                "Setup your username in settings",
            )
            return

        if self.user_id is None:
            self.user_id = self.twitch.get_user_id(
                self.settings.get_string("twitch-username")
            )
            if self.user_id is None:
                GLib.idle_add(
                    self.abort_refresh,
                    None,
                    "Cannot resolve Twitch username",
                    "Setup your username in settings",
                )
                return

        # fetch followed channels
        followed_channels = self.twitch.fetch_followed_channels(self.user_id)

        # Did an error occur?
        if isinstance(followed_channels, HTTPError):
            interval = self.settings.get_int("refresh-interval")
            GLib.idle_add(
                self.abort_refresh,
                followed_channels,
                "Cannot retrieve channel list from Twitch",
                f"Retrying in {interval} minutes...",
            )
            return

        # Are there channels that the user follows?
        elif followed_channels is None:
            return

        # Fetch live streams
        new_live_streams = self.twitch.fetch_live_streams(followed_channels)

        # Did an error occur?
        if isinstance(new_live_streams, HTTPError):
            interval = self.settings.get_int("refresh-interval")
            GLib.idle_add(
                self.abort_refresh,
                new_live_streams,
                "Cannot retrieve live streams from Twitch.tv",
                f"Retrying in {interval} minutes...",
            )
            return

        # Are there *live* streams?
        elif new_live_streams is None:
            return

        # Update menu with live streams
        GLib.idle_add(self.add_streams_menu, new_live_streams)

        # Re-enable "Check now" button
        GLib.idle_add(self.enable_menu)

        # Check which streams were not live before, create separate list for
        # notifications and update main livestreams list.
        # We check live streams by URL, because sometimes Twitch API does not
        # show stream status, which makes notifications appear even if stream
        # has been live before.
        notify_list = list(new_live_streams)
        for old_stream in self.live_streams:
            for new_stream in new_live_streams:
                if old_stream["url"] == new_stream["url"]:
                    notify_list[:] = [
                        d for d in notify_list if d.get("url") != new_stream["url"]
                    ]
                    break

        self.live_streams = new_live_streams

        # Push notifications of new streams
        if self.settings.get_boolean("enable-notifications"):
            self.push_notifications(notify_list)

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

        # Push notification
        Notify.init("Twitch Indicator")

        if isinstance(exception, HTTPError):
            message = str(exception.code) + ": " + message
        Notify.Notification.new(message, description, "error").show()

    def push_notifications(self, streams):
        """Pushes notifications of every stream, passed as a list of
        dictionaries.
        """

        for stream in streams:
            body = str(stream["title"])
            if self.settings.get_boolean("show-game-playing"):
                body = f"Currently playing: {stream['game']}\n{body}"

            Notify.init("Twitch Notification")
            notification = Notify.Notification.new(
                f"{stream['name']} just went LIVE!", body, ""
            )

            # Fixed deprecation warning
            notification.set_image_from_pixbuf(stream["pixbuf"].get_pixbuf())
            notification.show()

    def main(self):
        """Main indicator function."""
        Gtk.main()

    def quit(self, _):
        """Quits the applet."""
        self.timeout_thread.cancel()
        Gtk.main_quit()
