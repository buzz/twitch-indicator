import asyncio
import logging
import os
from typing import Optional

from gi.repository import Gio, Gtk

from twitch_indicator.actions import Actions
from twitch_indicator.api.api_manager import ApiManager
from twitch_indicator.constants import APP_ID, CACHE_DIR, CONFIG_DIR
from twitch_indicator.gui.gui_manager import GuiManager
from twitch_indicator.settings import Settings
from twitch_indicator.state import State

debug: bool = os.environ.get("TWITCH_INDICATOR_DEBUG", "false") == "true"
logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)


class TwitchIndicatorApp(Gtk.Application):
    """The main app."""

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

        self._logger: logging.Logger = logging.getLogger(__name__)

        self.actions: Actions = Actions(self)
        self.settings: Settings = Settings(self)
        self.state: State = State(self)
        self.settings.setup_event_handlers()
        self.gui_manager: GuiManager = GuiManager(self)
        self.api_manager: ApiManager = ApiManager(
            self, self.settings.get_double("refresh-interval")
        )

    def do_startup(self) -> None:
        """Start API and GUI manager."""
        self._logger.debug("do_startup()")
        Gtk.Application.do_startup(self)
        self._ensure_dirs()
        self.api_manager.run()
        self.gui_manager.run()

    def do_activate(self):
        pass

    def quit(self) -> None:
        """Close the indicator."""
        self._logger.debug("quit()")
        self.api_manager.quit()
        self.gui_manager.quit()

    def login(self, auth_event: Optional[asyncio.Event] = None) -> None:
        """Start auth flow."""
        if self.api_manager.loop is not None:
            # Acquire token
            coro = self.api_manager.login(auth_event)
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
    def _ensure_dirs() -> None:
        """Create app dirs if they don't exist."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
