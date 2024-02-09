import asyncio
import logging
import os
from threading import Thread
from time import sleep

from gi.repository import Gdk, GLib, Gtk

from twitch_indicator.constants import CACHE_DIR, CONFIG_DIR
from twitch_indicator.gui.channel_chooser import ChannelChooser
from twitch_indicator.gui.indicator import Indicator
from twitch_indicator.gui.notifications import Notifications
from twitch_indicator.gui.settings import Settings
from twitch_indicator.twitch.api_manager import ApiManager
from twitch_indicator.util import get_data_filepath

debug = os.environ.get("DEBUG", "0") == "1"
logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)


class TwitchIndicatorApp:
    """The main app."""

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self.ensure_dirs()

        self.followed_channels = []
        self.live_streams = []
        self.user_info = None

        self.settings = Settings(self)
        self.indicator = Indicator(self)
        self.notifications = Notifications(self.settings.get())
        self.channel_chooser = ChannelChooser(self)
        self.auth_dialog = None

        # API thread
        self.api_loop = asyncio.new_event_loop()
        self.api_manager = ApiManager(self)
        self.api_thread = Thread(target=self.api_loop.run_forever)

    def run(self):
        """Start asyncio and Gtk loop."""
        try:
            screen = Gdk.Screen.get_default()
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path(get_data_filepath("style.css"))
            Gtk.StyleContext.add_provider_for_screen(
                screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            self.api_thread.start()
            asyncio.run_coroutine_threadsafe(self.api_manager.run(), self.api_loop)
            Gtk.main()
        except KeyboardInterrupt:
            self.quit()

    def quit(self):
        """Close the indicator."""
        self._logger.debug("quit()")

        # Stop API thread event loop
        coro = self.api_manager.stop()
        fut = asyncio.run_coroutine_threadsafe(coro, self.api_loop)
        try:
            fut.result(timeout=5)
        except TimeoutError:
            self._logger.warn("quit(): Not all pending tasks were stopped")

        self.api_loop.call_soon_threadsafe(self.api_loop.stop)
        sleep(0.5)
        self.api_loop.call_soon_threadsafe(self.api_loop.close)
        self._logger.debug("quit(): API thread loop closed")

        # Stop API thread
        self.api_thread.join()
        self._logger.debug("quit(): API thread shut down")

        if self.auth_dialog:
            self.auth_dialog.destroy()
        if self.settings.dialog:
            self.settings.dialog.destroy()
        if self.channel_chooser.dialog:
            self.channel_chooser.dialog.destroy()

        Gtk.main_quit()

    def show_channel_chooser(self):
        """Show channel chooser dialog."""
        self.channel_chooser.show()

    def show_settings(self):
        """Show settings dialog."""
        self.settings.show()

    def show_auth_dialog(self, auth_event):
        """Show authentication dialog."""
        self.auth_dialog = Gtk.Dialog("Twitch authentication", None, 0)
        self.auth_dialog.add_buttons(
            Gtk.STOCK_QUIT, Gtk.ResponseType.CANCEL, "Authorize", Gtk.ResponseType.OK
        )
        self.auth_dialog.set_position(Gtk.WindowPosition.CENTER)

        builder = Gtk.Builder()
        builder.add_from_file(get_data_filepath("twitch-indicator-auth.glade"))

        box = self.auth_dialog.get_content_area()
        box.add(builder.get_object("grid"))

        response = self.auth_dialog.run()
        try:
            if response == Gtk.ResponseType.OK:
                coro = self.api_manager.acquire_token(auth_event)
                asyncio.run_coroutine_threadsafe(coro, self.api_loop)
            else:
                GLib.idle_add(self.quit)
        finally:
            self.auth_dialog.destroy()
            self.auth_dialog = None

    def not_authorized(self, auth_event):
        """Clear cache and show authentication dialog."""
        self.user_info = None
        self.show_auth_dialog(auth_event)

    def update_user_info(self, user_info):
        """Update user info."""
        self.user_info = user_info

    def update_followed_channels(self, followed_channels):
        """Update followed channels."""
        self.followed_channels = followed_channels

    @staticmethod
    def ensure_dirs():
        """Create app dirs if they don't exist."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
