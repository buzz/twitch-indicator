import asyncio
import logging
import os

from gi.repository import Gio

from twitch_indicator.api.api_manager import ApiManager
from twitch_indicator.constants import CACHE_DIR, CONFIG_DIR, SETTINGS_KEY
from twitch_indicator.gui.gui_manager import GuiManager

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

        self.settings = Gio.Settings.new(SETTINGS_KEY)
        self.gui_manager = GuiManager(self)
        self.api_manager = ApiManager(self)

    def run(self):
        """Start API and GUI manager."""
        try:
            self.api_manager.run()
            self.gui_manager.run()
        except KeyboardInterrupt:
            self.quit()

    def quit(self):
        """Close the indicator."""
        self._logger.debug("quit()")
        self.api_manager.quit()
        self.gui_manager.quit()

    def not_authorized(self, auth_event):
        """Show authentication dialog."""
        self.user_info = None
        self.gui_manager.show_auth_dialog(auth_event)

    def start_auth(self, auth_event):
        """Start auth flow."""
        coro = self.api_manager.acquire_token(auth_event)
        asyncio.run_coroutine_threadsafe(coro, self.api_manager.loop)

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
