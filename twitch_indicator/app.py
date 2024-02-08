import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import os

from gi.repository import GLib, Gtk

from twitch_indicator.channel_chooser import ChannelChooser
from twitch_indicator.constants import CONFIG_DIR
from twitch_indicator.indicator import Indicator
from twitch_indicator.notifications import Notifications
from twitch_indicator.settings import Settings
from twitch_indicator.twitch.api_thread import ApiThread
from twitch_indicator.util import get_data_filepath

debug = os.environ.get("DEBUG", "0") == "1"
logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)


class TwitchIndicatorApp:
    """The main app."""

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self.ensure_config_dir()

        self.followed_channels = []
        self.live_streams = []
        self.user_id = None

        self.settings = Settings(self)
        self.indicator = Indicator(self)
        self.notifications = Notifications(self.settings.get())
        self.channel_chooser = ChannelChooser(self)

        # API thread
        self.shutdown_event = asyncio.Event()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.api_loop = asyncio.new_event_loop()
        self.api_thread = ApiThread(self)
        self.executor.submit(self.api_thread.start)

    @staticmethod
    def run():
        """Start Gtk main loop."""
        Gtk.main()

    def quit(self):
        """Close the indicator."""
        self._logger.debug("quit()")

        # Stop API thread event loop and thread
        if self.api_loop.is_running():
            try:
                coro = self.api_thread.stop()
                future = asyncio.run_coroutine_threadsafe(coro, self.api_loop)
                future.result(timeout=2)
            except TimeoutError:
                pass
        self.executor.shutdown(cancel_futures=True)

        if self.settings.dialog:
            self.settings.dialog.destroy()
        if self.channel_chooser.dialog:
            self.channel_chooser.dialog.destroy()

        Gtk.main_quit()

    def clear_cache(self):
        """Clear cache."""
        self.user_id = None
        self.notifications.first_notification_run = True
        self.api_loop.call_soon_threadsafe(self.api_thread.clear_cache)

    def show_channel_chooser(self):
        """Show channel chooser dialog."""
        self.channel_chooser.show()

    def show_settings(self):
        """Show settings dialog."""
        self.settings.show()

    def show_auth_dialog(self, auth_event):
        """Show authentication dialog."""
        dialog = Gtk.Dialog("Twitch authentication", None, 0)
        dialog.add_buttons(
            Gtk.STOCK_QUIT, Gtk.ResponseType.CANCEL, "Authorize", Gtk.ResponseType.OK
        )
        dialog.set_position(Gtk.WindowPosition.CENTER)

        builder = Gtk.Builder()
        builder.add_from_file(get_data_filepath("twitch-indicator-auth.glade"))

        box = dialog.get_content_area()
        box.add(builder.get_object("grid"))

        response = dialog.run()
        try:
            if response == Gtk.ResponseType.OK:
                coro = self.api_thread.acquire_token(auth_event)
                asyncio.run_coroutine_threadsafe(coro, self.api_loop)
            else:
                GLib.idle_add(self.quit)
        finally:
            dialog.destroy()

    def not_authorized(self, auth_event):
        """Clear cache and show authentication dialog."""
        self.clear_cache()
        self.show_auth_dialog(auth_event)

    @staticmethod
    def ensure_config_dir():
        """Create config dir if it doesn't exist."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
