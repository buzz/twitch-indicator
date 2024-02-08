import asyncio
import logging

from gi.repository import GLib

from twitch_indicator.twitch.api import TwitchApi
from twitch_indicator.twitch.auth import Auth


class ApiManager:
    def __init__(self, app):
        self._logger = logging.getLogger(__name__)
        self.user_info = None
        self.app = app
        self.loop = self.app.api_loop
        self.followers_fetched = False
        self.auth = Auth()
        self.api = TwitchApi(self)

    async def stop(self):
        """Stop pending tasks."""
        self._logger.debug("stop()")
        tasks = [t for t in asyncio.all_tasks() if t != asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def run(self):
        """API thread main coroutine."""
        try:
            self._logger.debug("run()")

            await self.auth.restore_token()
            self.user_info = await self.api.get_user_info()
            self._logger.debug(f"Got user info: {self.user_info}")

            GLib.idle_add(self.app.update_user_info, self.user_info)

            self._logger.debug("Get followed channels")
            followed_channels = await self.api.fetch_followed_channels(
                self.user_info["id"]
            )
            for c in followed_channels:
                print(f"ID={c['id']} Name={c['name']}")
        except Exception as e:
            self._logger.exception(e)
        finally:
            self._logger.debug("run(): task done")

    async def acquire_token(self, auth_event):
        """Acquire auth token."""
        try:
            await self.auth.acquire_token(auth_event)
        except Exception as e:
            self._logger.exception(e)
        finally:
            self._logger.debug("acquire_token(): task done")

    def clear_cache(self):
        """Clear API cache."""
        self.api.clear_cache()
