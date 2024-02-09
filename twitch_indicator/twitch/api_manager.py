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

            # Restore token
            await self.auth.restore_token()

            # Validate token
            self.user_info = await self.api.validate()
            self._logger.debug(f"run(): Validated: {self.user_info}")
            GLib.idle_add(self.app.update_user_info, self.user_info)

            # Get user info
            # self.user_info = await self.api.get_user_info()
            # self._logger.debug(f"run(): Got user info: {self.user_info}")

            # Get followed channels
            followed_channels = await self.api.fetch_followed_channels(
                self.user_info["user_id"]
            )
            self._logger.debug("run(): Got followed channels")
            GLib.idle_add(self.app.update_followed_channels, followed_channels)

            # Get live streams
            live_streams = await self.api.fetch_live_streams(self.user_info["user_id"])
            self._logger.debug(f"run(): Got live streams ({len(live_streams)})")
            for channel in live_streams:
                print(
                    f"channel: {channel['user_name']} ({channel['user_id']}) - Category: {channel['game_name']} - Title: {channel['title']} - Viewers: {channel['viewer_count']}"
                )
            GLib.idle_add(self.app.indicator.add_streams_menu, live_streams)

            # Ensure current profile pictures
            await self.api.fetch_profile_pictures(live_streams)

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
