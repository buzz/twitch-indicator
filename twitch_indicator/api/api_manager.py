import asyncio
import logging
from threading import Thread
from time import sleep

from gi.repository import GLib

from twitch_indicator.api.twitch_api import TwitchApi
from twitch_indicator.api.twitch_auth import Auth
from twitch_indicator.constants import REFRESH_INTERVAL_LIMITS
from twitch_indicator.util import coro_exception_handler


class ApiManager:
    def __init__(self, app, refresh_interval):
        self._logger = logging.getLogger(__name__)
        self.app = app
        self.loop = None
        self._thread = None
        self._refresh_interval = refresh_interval
        self._periodic_polling_task = None

        self.auth = Auth()
        self.api = TwitchApi(self)

    def run(self):
        """Start asyncio event loop."""
        self.loop = asyncio.new_event_loop()
        self._thread = Thread(target=self.loop.run_forever)
        self._thread.start()
        fut = asyncio.run_coroutine_threadsafe(self._start(), self.loop)
        fut.add_done_callback(coro_exception_handler)

    def quit(self):
        """Shut down manager."""
        self._logger.debug("quit()")

        # Stop API thread event loop
        fut = asyncio.run_coroutine_threadsafe(self._stop(), self.loop)
        try:
            fut.result(timeout=5)
        except TimeoutError:
            self._logger.warn("quit(): Not all pending tasks were stopped")
        except Exception as exc:
            self._logger.exception("quit(): Exception raised", exc_info=exc)
        self.loop.call_soon_threadsafe(self.loop.stop)
        sleep(0.1)
        self.loop.call_soon_threadsafe(self.loop.close)
        self._logger.debug("quit(): API thread event loop closed")

        # Stop API thread
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise RuntimeError("Could not shut down API thread")
        self._logger.debug("quit(): API thread shut down")

    async def acquire_token(self, auth_event):
        """Acquire auth token."""
        await self.auth.acquire_token(auth_event)

    def update_refresh_interval(self, refresh_interval):
        self._logger.debug(f"update_refresh_interval(): {refresh_interval}")
        old_refresh_interval = self._refresh_interval
        self._refresh_interval = refresh_interval
        if self._refresh_interval != old_refresh_interval:
            self.loop.create_task(self._restart_periodic_polling())

    async def _start(self):
        """API thread main coroutine."""
        self._logger.debug("_start()")

        # Restore token
        await self.auth.restore_token()

        # Validate token
        user_info = await self.api.validate()
        self._logger.debug(f"run(): Validated: {user_info}")
        GLib.idle_add(self.app.state.set_user_info, user_info)

        # Start periodic token validation
        self.loop.create_task(self._periodic_validate())

        await self._refresh_followed_channels(user_info["user_id"])

        # Get followed live streams
        live_streams = await self.api.fetch_followed_streams(user_info["user_id"])
        self._logger.debug(f"run(): live streams: {len(live_streams)}")

        # Ensure current profile pictures
        await self.api.fetch_profile_pictures(s["user_id"] for s in live_streams)

        GLib.idle_add(self.app.state.set_live_streams, live_streams)

        # Start stream polling cycle
        await self._restart_periodic_polling()

    async def _stop(self):
        """Stop pending tasks and thread."""
        self._logger.debug("_stop()")
        tasks = [t for t in asyncio.all_tasks() if t != asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _restart_periodic_polling(self):
        """(Re)start periodic polling."""
        self._logger.debug("_restart_periodic_polling()")

        # Cancel old task
        if (
            self._periodic_polling_task is not None
            and not self._periodic_polling_task.done()
        ):
            self._periodic_polling_task.cancel()
            try:
                await self._periodic_polling_task
            except asyncio.CancelledError:
                pass

        self._periodic_polling_task = self.loop.create_task(self._periodic_polling())

    async def _periodic_polling(self):
        """Poll followed streams periodically."""

        RI_MIN = int(REFRESH_INTERVAL_LIMITS[0] * 60)
        RI_MAX = int(REFRESH_INTERVAL_LIMITS[1] * 60)
        delay = max(min(int(self._refresh_interval * 60), RI_MAX), RI_MIN)

        while True:
            await asyncio.sleep(delay)

            with self.app.state.locks["user_info"]:
                user_id = self.app.state.user_info["user_id"]

            live_streams = await self.api.fetch_followed_streams(user_id)
            msg = f"_periodic_polling(): live streams: {len(live_streams)}"
            self._logger.debug(msg)

            await self.api.fetch_profile_pictures((s["user_id"] for s in live_streams))

            GLib.idle_add(self.app.state.set_live_streams, live_streams)

    async def _refresh_followed_channels(self, user_id=None):
        """Refresh followed channels list."""
        self._logger.debug("refresh_followed_channels()")

        if user_id is None:
            with self.app.state.locks["user_info"]:
                user_id = self.app.state.user_info["user_id"]

        followed_channels = await self.api.fetch_followed_channels(user_id)
        GLib.idle_add(self.app.state.set_followed_channels, followed_channels)

    async def _periodic_validate(self):
        """
        Validate token every hour as required by Twitch API.

        https://dev.twitch.tv/docs/authentication/validate-tokens/
        """
        while True:
            await asyncio.sleep(3600)  # 1 hour
            user_info = await self.api.validate()
            self._logger.debug(f"_periodic_validate(): Validated: {user_info}")
