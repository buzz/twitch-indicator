import asyncio
import logging
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING, Any, Optional

import aiohttp
from gi.repository import GLib

from twitch_indicator.api.models import ValidationInfo
from twitch_indicator.api.twitch_api import TwitchApi
from twitch_indicator.api.twitch_auth import Auth
from twitch_indicator.constants import REFRESH_INTERVAL_LIMITS, TWITCH_VALIDATION_INTERVAL
from twitch_indicator.utils import coro_exception_handler

if TYPE_CHECKING:
    from twitch_indicator.app import TwitchIndicatorApp


class ApiManager:
    def __init__(self, app: "TwitchIndicatorApp", refresh_interval: float) -> None:
        self._logger = logging.getLogger(__name__)
        self.app = app
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[Thread] = None
        self._refresh_interval = refresh_interval
        self._periodic_polling_task: Optional[asyncio.Task[None]] = None
        self._validate_later_task: Optional[asyncio.Task[None]] = None

        self.auth = Auth()
        self.api = TwitchApi(self)

        self.app.state.add_handler("validation_info", self._on_validation_info_changed)

    def run(self) -> None:
        """Start asyncio event loop."""
        self.loop = asyncio.new_event_loop()
        self.loop.set_exception_handler(self._handle_exception)
        self.api.set_session(aiohttp.ClientSession(loop=self.loop))
        self._thread = Thread(target=self.loop.run_forever)
        self._thread.start()
        fut = asyncio.run_coroutine_threadsafe(self._start(), self.loop)
        fut.add_done_callback(coro_exception_handler)

    def quit(self) -> None:
        """Shut down manager."""
        self._logger.debug("quit()")

        # Stop API thread event loop
        if self.loop is not None:
            fut = asyncio.run_coroutine_threadsafe(self._stop(), self.loop)
            try:
                fut.result(timeout=5)
            except TimeoutError:
                self._logger.warning("quit(): Not all pending tasks were stopped")
            except Exception as exc:
                self._logger.exception("quit(): Exception raised", exc_info=exc)
            self.loop.call_soon_threadsafe(self.loop.stop)
            sleep(0.1)
            self.loop.call_soon_threadsafe(self.loop.close)
            self._logger.debug("quit(): API thread event loop closed")

        # Stop API thread
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("Could not shut down API thread")
            self._logger.debug("quit(): API thread shut down")

    async def login(self, auth_event: Optional[asyncio.Event]) -> None:
        """Start auth flow."""
        await self.auth.acquire_token(auth_event)
        await self.validate()

    async def acquire_token(self, auth_event: Optional[asyncio.Event]) -> None:
        """Acquire auth token."""
        await self.auth.acquire_token(auth_event)

    def update_refresh_interval(self, refresh_interval: float) -> None:
        self._logger.debug("update_refresh_interval(): %f", refresh_interval)
        old_refresh_interval = self._refresh_interval
        self._refresh_interval = refresh_interval
        if self.loop is not None and self._refresh_interval != old_refresh_interval:
            self.loop.create_task(self._restart_periodic_polling())

    async def validate(self) -> None:
        """Validate API token."""
        validation_info = await self.api.validate()
        self._logger.debug("validate(): Validated: %d", validation_info.user_id)
        GLib.idle_add(self.app.state.set_validation_info, validation_info)

    async def _start(self) -> None:
        """API thread main coroutine."""
        self._logger.debug("_start()")
        await self.auth.restore_token()
        await self.validate()

    async def _stop(self) -> None:
        """Stop pending tasks and thread."""
        self._logger.debug("_stop()")

        # Close client session
        await self.api.close_session()

        # Cancel and gather remaining tasks
        tasks = [t for t in asyncio.all_tasks() if t != asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _on_validation_info_changed(self, validation_info: ValidationInfo) -> None:
        """Continue request flow after successful validation."""
        self._logger.debug("_on_validation_info_changed()")

        if self.loop is None:
            raise RuntimeError("No event loop")

        # Cancel validation later task
        if self._validate_later_task is not None:
            self._validate_later_task.cancel()
            try:
                await self._validate_later_task
            except asyncio.CancelledError:
                pass

        # Cancel periodic polling task
        if self._periodic_polling_task is not None and not self._periodic_polling_task.done():
            self._periodic_polling_task.cancel()
            try:
                await self._periodic_polling_task
            except asyncio.CancelledError:
                pass

        with self.app.state.locks["validation_info"]:
            # Nothing to do if validation failed
            if validation_info is None:
                return
            user_id = validation_info.user_id

        # Get logged in user info
        (user,) = await self.api.fetch_users([user_id])
        self._logger.debug("run(): Got logged in user: %d", user.id)
        GLib.idle_add(self.app.state.set_user, user)

        # Ensure user profile pic
        await self.api.fetch_profile_pictures((user_id,))

        # Get followed channels
        await self._refresh_followed_channels(user_id)

        # Get followed live streams
        await self._refresh_live_streams()

        # Start stream polling cycle
        await self._restart_periodic_polling()

        # Start next periodic token validation
        self._validate_later_task = self.loop.create_task(self._validate_later())

        # Allow notifications to happen from this point on
        GLib.idle_add(self.app.state.set_first_run, False)

    async def _restart_periodic_polling(self) -> None:
        """(Re)start periodic polling."""
        self._logger.debug("_restart_periodic_polling()")

        # Cancel old task
        if self._periodic_polling_task is not None and not self._periodic_polling_task.done():
            self._periodic_polling_task.cancel()
            try:
                await self._periodic_polling_task
            except asyncio.CancelledError:
                pass

        if self.loop is not None:
            coro = self._periodic_polling()
            self._periodic_polling_task = self.loop.create_task(coro)

    async def _periodic_polling(self) -> None:
        """Poll followed live streams periodically."""

        RI_MIN = int(REFRESH_INTERVAL_LIMITS[0] * 60)
        RI_MAX = int(REFRESH_INTERVAL_LIMITS[1] * 60)
        delay = max(min(int(self._refresh_interval * 60), RI_MAX), RI_MIN)

        while True:
            await asyncio.sleep(delay)
            await self._refresh_live_streams()

    async def _refresh_live_streams(self) -> None:
        """Refresh followed live streams."""
        with self.app.state.locks["validation_info"]:
            if self.app.state.validation_info is None:
                self._logger.warning("_refresh_live_streams(): No user info set")
                return
            user_id = self.app.state.validation_info.user_id

        live_streams = await self.api.fetch_followed_streams(user_id)
        msg = "_refresh_live_streams(): live streams: %d"
        self._logger.debug(msg, len(live_streams))

        # Ensure current profile pictures
        await self.api.fetch_profile_pictures(s.user_id for s in live_streams)

        # Send live stream to GUI
        GLib.idle_add(self.app.state.set_live_streams, live_streams)

    async def _refresh_followed_channels(self, user_id: int) -> None:
        """Refresh followed channels list."""
        self._logger.debug("refresh_followed_channels()")
        followed_channels = await self.api.fetch_followed_channels(user_id)
        GLib.idle_add(self.app.state.set_followed_channels, followed_channels)

    async def _validate_later(self) -> None:
        """
        Validate token periodically as required by the Twitch API.

        https://dev.twitch.tv/docs/authentication/validate-tokens/
        """
        await asyncio.sleep(TWITCH_VALIDATION_INTERVAL)
        await self.validate()

    def _handle_exception(self, loop: asyncio.AbstractEventLoop, context: dict[str, Any]):
        """Handle exceptions created by create_task."""
        try:
            exc = context["exception"]
            self._logger.exception("_exception_handler(): Caught exception:", exc_info=exc)
        except KeyError:
            self._logger.error(f"_exception_handler(): {context['message']}")

        self._logger.info("_exception_handler(): Shutting down...")
        GLib.idle_add(self.app.quit)
