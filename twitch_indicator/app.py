import asyncio
import logging
import os

from twitch_indicator.api.api_manager import ApiManager
from twitch_indicator.constants import CACHE_DIR, CONFIG_DIR
from twitch_indicator.gui.gui_manager import GuiManager
from twitch_indicator.settings import Settings
from twitch_indicator.state import State

debug = os.environ.get("TWITCH_INDICATOR_DEBUG", "false") == "true"
logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)


class TwitchIndicatorApp:
    """The main app."""

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self.ensure_dirs()

        self.settings = Settings(self)
        self.state = State(self)
        self.settings.setup_event_handler()
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
        self.state.set_user_info(None)
        self.state.set_followed_channels([])
        self.state.set_live_streams([])
        self.gui_manager.show_auth_dialog(auth_event)

    def start_auth(self, auth_event):
        """Start auth flow."""
        coro = self.api_manager.acquire_token(auth_event)
        fut = asyncio.run_coroutine_threadsafe(coro, self.api_manager.loop)
        try:
            fut.result()
        except Exception as exc:
            self._logger.exception("start_auth(): Exception raised", exc_info=exc)
            self.quit()

    @staticmethod
    def ensure_dirs():
        """Create app dirs if they don't exist."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
