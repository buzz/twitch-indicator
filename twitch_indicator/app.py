import threading
from urllib.error import URLError

from gi.repository import GLib, Gtk

from twitch_indicator.auth import Auth
from twitch_indicator.channel_chooser import ChannelChooser
from twitch_indicator.errors import NotAuthorizedException
from twitch_indicator.indicator import Indicator
from twitch_indicator.notifications import Notifications
from twitch_indicator.settings import Settings
from twitch_indicator.twitch import TwitchApi


class TwitchIndicatorApp:
    """The main app."""

    def __init__(self):
        self.followed_channels = []
        self.live_streams = []
        self.user_id = None

        # Threads
        self.api_thread = None
        self.timer_thread = None

        self.settings = Settings(self)
        self.auth = Auth(self)
        self.api = TwitchApi(self.auth)
        self.indicator = Indicator(self)
        self.notifications = Notifications(self.settings.get())
        self.channel_chooser = ChannelChooser(self)

        self.start_api_thread()

    @staticmethod
    def run():
        """Start Gtk main loop."""
        Gtk.main()

    def quit(self):
        """Close the indicator."""
        if self.timer_thread:
            self.timer_thread.cancel()
        if self.settings.dialog:
            self.settings.dialog.destroy()
        if self.channel_chooser.dialog:
            self.channel_chooser.dialog.destroy()
        Gtk.main_quit()

    def clear_cache(self):
        """Clear cache."""
        self.user_id = None
        self.notifications.first_notification_run = True
        self.api.clear_cache()

    def start_api_thread(self):
        """Start API thread."""
        if self.api_thread and self.api_thread.is_alive():
            self.api_thread.join()
        self.api_thread = threading.Thread(
            daemon=True, name="api-thread", target=self.refresh_streams
        )
        self.api_thread.start()

    def start_timer(self):
        """Start timer thread."""
        self.timer_thread = threading.Timer(
            self.settings.get().get_int("refresh-interval") * 60,
            self.refresh_streams,
        )
        self.timer_thread.start()

    def show_channel_chooser(self):
        """Show channel chooser dialog."""
        self.channel_chooser.show()

    def show_settings(self):
        """Show settings dialog."""
        self.settings.show()

    def refresh_streams(self):
        """Refresh live streams list. Also push notifications when needed."""
        settings = self.settings.get()

        if self.timer_thread:
            self.timer_thread.cancel()

        GLib.idle_add(self.indicator.disable_check_now)

        # Get Twitch user ID
        if self.user_id is None:
            try:
                self.user_id = self.api.get_user_id()
            except NotAuthorizedException:
                GLib.idle_add(self.not_authorized)
                return
            except URLError as err:
                self.refresh_failed("Cannot retrieve user ID from Twitch", err)
                return

        # Fetch followed channels
        try:
            self.followed_channels = self.api.fetch_followed_channels(self.user_id)
        except NotAuthorizedException:
            GLib.idle_add(self.not_authorized)
            return
        except URLError as err:
            self.refresh_failed("Cannot retrieve channel list from Twitch", err)
            return

        # Are there channels that the user follows?
        if self.followed_channels:
            GLib.idle_add(self.settings.enable_channel_chooser)

            # Fetch live streams
            try:
                new_live_streams = self.api.fetch_live_streams(
                    [ch["id"] for ch in self.followed_channels]
                )
            except NotAuthorizedException:
                GLib.idle_add(self.not_authorized)
                return
            except URLError as err:
                self.refresh_failed("Cannot retrieve live streams from Twitch", err)
                return

            # Are there *live* streams?
            if new_live_streams:

                # Update menu with live streams
                GLib.idle_add(self.indicator.add_streams_menu, new_live_streams)

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
                                d
                                for d in notify_list
                                if d.get("url") != new_stream["url"]
                            ]
                            break

                self.live_streams = new_live_streams

                # Only show notifications for enabled streams
                notify_list = [
                    stream
                    for stream in notify_list
                    if stream["id"] not in self.channel_chooser.enabled_channel_ids
                    or self.channel_chooser.enabled_channel_ids[stream["id"]]
                ]

                # Push notifications of new streams
                if settings.get_boolean("enable-notifications"):
                    GLib.idle_add(self.notifications.show_streams, notify_list)

        self.indicator.first_fetch = False

        # Schedule next periodic fetch
        GLib.idle_add(self.start_timer)

        # Re-enable "Check now" button
        GLib.idle_add(self.indicator.enable_check_now)

    def refresh_failed(self, msg, err):
        """Handle network error while fetching data."""
        interval = self.settings.get().get_int("refresh-interval")
        GLib.idle_add(
            self.indicator.abort_refresh,
            err,
            msg,
            f"Retrying in {interval} minutes...",
        )
        GLib.idle_add(self.start_timer)

    def not_authorized(self):
        """Clear cache and request authorization."""
        self.clear_cache()
        self.auth.show_dialog()
