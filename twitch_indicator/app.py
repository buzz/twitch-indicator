import asyncio
import logging
import os
from typing import Optional

from twitch_indicator.actions import Actions
from twitch_indicator.api.api_manager import ApiManager
from twitch_indicator.constants import CACHE_DIR, CONFIG_DIR
from twitch_indicator.gui.gui_manager import GuiManager
from twitch_indicator.settings import Settings
from twitch_indicator.state import State

debug: bool = os.environ.get("TWITCH_INDICATOR_DEBUG", "false") == "true"
logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)


class TwitchIndicatorApp:
    """The main app."""

    def __init__(self) -> None:
        self._logger: logging.Logger = logging.getLogger(__name__)
        self.ensure_dirs()

        self.actions: Actions = Actions(self)
        self.settings: Settings = Settings(self)
        self.state: State = State(self)
        self.settings.setup_event_handlers()
        self.gui_manager: GuiManager = GuiManager(self)
        self.api_manager: ApiManager = ApiManager(
            self, self.settings.get_double("refresh-interval")
        )

    def run(self) -> None:
        """Start API and GUI manager."""
        try:
            self.api_manager.run()
            self.gui_manager.run()
        except KeyboardInterrupt:
            self.quit()

    def quit(self) -> None:
        """Close the indicator."""
        self._logger.debug("quit()")
        self.api_manager.quit()
        self.gui_manager.quit()

    def login(self, auth_event: Optional[asyncio.Event] = None) -> None:
        """Start auth flow."""
        if self.api_manager.loop is not None:
            # Acquire token
            coro = self.api_manager.acquire_token(auth_event)
            fut = asyncio.run_coroutine_threadsafe(coro, self.api_manager.loop)
            try:
                fut.result()
            except Exception as exc:
                self._logger.exception("start_auth(): Exception raised", exc_info=exc)
                return

            # Validate token
            coro = self.api_manager.validate()
            fut = asyncio.run_coroutine_threadsafe(coro, self.api_manager.loop)
            try:
                fut.result()
            except Exception as exc:
                self._logger.exception("start_auth(): Exception raised", exc_info=exc)
                return

    def logout(self) -> None:
        """Log out user."""
        self._logger.debug("logout()")
        self.state.reset()
        if self.api_manager.loop is not None:
            coro = self.api_manager.auth.logout()
            asyncio.run_coroutine_threadsafe(coro, self.api_manager.loop)

    @staticmethod
    def ensure_dirs() -> None:
        """Create app dirs if they don't exist."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
