import asyncio
import logging
import traceback

from gi.repository import GLib

from twitch_indicator.errors import NotAuthorizedException
from twitch_indicator.twitch.api import TwitchApi
from twitch_indicator.twitch.auth import Auth


class ApiThread:
    def __init__(self, app):
        self._logger = logging.getLogger(__name__)
        self.user_info = None
        self.app = app
        self.loop = self.app.api_loop
        self.shutdown_event = self.app.shutdown_event
        self.followers_fetched = False
        self.auth = Auth()
        self.api = TwitchApi(self)

    def start(self):
        """Start API thread task."""
        self._logger.debug("start()")
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run())

    async def stop(self):
        """Stop API thread event loop."""
        self._logger.debug("stop()")
        self.shutdown_event.set()
        await asyncio.sleep(0.5)  # Allow tasks to finish
        self.loop.stop()

    async def run(self):
        try:
            self._logger.debug("run()")

            await self.auth.restore_token()
            self.user_info = await self.api.get_user_info()
            self._logger.debug(f"Got user info: {self.user_info}")

            self._logger.debug("Get followed channels")
            followed_channels = await self.api.fetch_followed_channels(
                self.user_info["id"]
            )
            for c in followed_channels:
                print(f"ID={c['id']} Name={c['name']}")
        except asyncio.CancelledError:
            self._logger.debug("run task cancelled")
            raise
        except Exception:
            self._logger.exception(traceback.format_exc())
        finally:
            GLib.idle_add(self.app.quit)

    async def acquire_token(self, auth_event):
        try:
            await self.auth.acquire_token(auth_event)
        except Exception:
            self._logger.exception(traceback.format_exc())

    def clear_cache(self):
        self.api.clear_cache()
