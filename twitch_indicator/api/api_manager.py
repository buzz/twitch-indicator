import asyncio
import logging
from threading import Thread
from time import sleep

from gi.repository import GLib

from twitch_indicator.api.twitch_api import TwitchApi
from twitch_indicator.api.twitch_auth import Auth


class ApiManager:
    def __init__(self, app):
        self._logger = logging.getLogger(__name__)
        self.user_info = None
        self.app = app
        self.loop = None
        self._thread = None

        self.auth = Auth()
        self.api = TwitchApi(self)

    def run(self):
        """Start asyncio event loop."""
        self.loop = asyncio.new_event_loop()
        self._thread = Thread(target=self.loop.run_forever)
        self._thread.start()
        asyncio.run_coroutine_threadsafe(self._start(), self.loop)

    def quit(self):
        """Shut down manager."""
        # Stop API thread event loop
        try:
            fut = asyncio.run_coroutine_threadsafe(self._stop(), self.loop)
            fut.result(timeout=5)
        except TimeoutError:
            self._logger.warn("quit(): Not all pending tasks were stopped")
        self.loop.call_soon_threadsafe(self.loop.stop)
        sleep(0.5)
        self.loop.call_soon_threadsafe(self.loop.close)
        self._logger.debug("quit(): API thread event loop closed")

        # Stop API thread
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise RuntimeError("Could not shut down API thread")
        self._logger.debug("quit(): API thread shut down")

    async def acquire_token(self, auth_event):
        """Acquire auth token."""
        try:
            await self.auth.acquire_token(auth_event)
        except Exception as e:
            self._logger.exception(e)
        finally:
            self._logger.debug("acquire_token(): task done")

    async def _start(self):
        """API thread main coroutine."""
        try:
            self._logger.debug("run()")

            # Restore token
            await self.auth.restore_token()

            # Validate token
            self.user_info = await self.api.validate()
            self._logger.debug(f"run(): Validated: {self.user_info}")
            GLib.idle_add(self.app.update_user_info, self.user_info)

            # Get followed channels
            followed_channels = await self.api.fetch_followed_channels(
                self.user_info["user_id"]
            )
            self._logger.debug("run(): Got followed channels")
            GLib.idle_add(self.app.update_followed_channels, followed_channels)

            # Get live streams
            live_streams = await self.api.fetch_live_streams(self.user_info["user_id"])
            self._logger.debug(f"run(): Got live streams ({len(live_streams)})")
            GLib.idle_add(self.app.gui_manager.indicator.add_streams_menu, live_streams)

            # Ensure current profile pictures
            await self.api.fetch_profile_pictures(live_streams)

        except Exception as e:
            self._logger.exception(e)
        finally:
            self._logger.debug("run(): task done")

    async def _stop(self):
        """Stop pending tasks and thread."""
        self._logger.debug("stop()")
        tasks = [t for t in asyncio.all_tasks() if t != asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
