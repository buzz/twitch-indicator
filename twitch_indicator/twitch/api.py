import asyncio
import logging
from urllib.parse import urlencode, urlparse, urlunparse

import aiohttp
from gi.repository import GLib

from twitch_indicator.cached_profile_image import CachedProfileImage
from twitch_indicator.constants import (
    DEFAULT_AVATAR,
    TWITCH_API_LIMIT,
    TWITCH_API_URL,
    TWITCH_WEB_URL,
    TWITCH_CLIENT_ID,
)
from twitch_indicator.errors import NotAuthorizedException


class TwitchApi:
    """Access Twitch API."""

    def __init__(self, api_thread):
        self._logger = logging.getLogger(__name__)
        self.api_thread = api_thread
        self.channel_info_cache = {}
        self.game_info_cache = {}

    def clear_cache(self):
        """Clear channel info and game info cache."""
        self.channel_info_cache.clear()
        self.game_info_cache.clear()
        self._logger.debug("Cache cleared")

    async def fetch_followed_channels(self, user_id):
        """Fetch user followed channels and return a list with channel ids."""
        loc = "channels/followed"
        url = self.build_url(loc, {"user_id": user_id})
        resp = await self.get_api_response(url)

        total = int(resp["total"])
        fetched = len(resp["data"])
        data = resp["data"]

        # User has not followed any channels
        if total == 0:
            return None

        last = resp
        while fetched < total:
            url = self.build_url(
                loc,
                {"after": last["pagination"]["cursor"], "user_id": user_id},
            )
            nxt = await self.get_api_response(url)

            fetched += len(nxt["data"])
            data += nxt["data"]
            last = nxt

        return [
            {"id": int(data["broadcaster_id"]), "name": data["broadcaster_name"]}
            for data in data
        ]

    def fetch_live_streams(self, channel_ids):
        """
        Fetch live streams and return as list of dictionaries.
        """
        channel_index = 0
        channel_max = TWITCH_API_LIMIT
        channels_live = []

        while channel_index < len(channel_ids):
            curr_channels = channel_ids[channel_index:channel_max]
            channel_index += len(curr_channels)
            channel_max += TWITCH_API_LIMIT

            params = [("user_id", user_id) for user_id in curr_channels]
            url = self.build_url("streams", params)
            resp = self.get_api_response(url)

            for channel in resp["data"]:
                channels_live.append(channel)

        streams = []
        for stream in channels_live:
            user_id = int(stream["user_id"])
            channel_info = self.get_channel_info(user_id)
            try:
                game_info = self.get_game_info(int(stream["game_id"]))
            except ValueError:
                game_info = {"name": "[Unknown game]"}

            stream = {
                "id": user_id,
                "name": channel_info["display_name"],
                "game": game_info["name"],
                "title": stream["title"],
                "image": channel_info["profile_image_url"],
                "pixbuf": channel_info["pixbuf"],
                "url": f"{TWITCH_WEB_URL}{channel_info['login']}",
                "viewer_count": stream["viewer_count"],
            }
            streams.append(stream)

        return streams

    def get_channel_info(self, channel_id):
        """Get channel info."""
        try:
            return self.channel_info_cache[channel_id]
        except KeyError:
            url = self.build_url("users", {"id": channel_id})
            resp = self.get_api_response(url)
            if not len(resp["data"]) == 1:
                return ValueError("Bad API response.")
            channel_info = resp["data"][0]

            # Channel image
            if channel_info["profile_image_url"]:
                channel_info["pixbuf"] = CachedProfileImage.new_from_profile_url(
                    channel_id, channel_info["profile_image_url"]
                )
            else:
                channel_info["pixbuf"] = CachedProfileImage.new_from_profile_url(
                    "default", DEFAULT_AVATAR
                )

            self.channel_info_cache[channel_id] = channel_info
            return channel_info

    def get_game_info(self, game_id):
        """Get game info."""
        try:
            return self.game_info_cache[game_id]
        except KeyError:
            url = self.build_url("games", {"id": game_id})
            resp = self.get_api_response(url)
            if not len(resp["data"]) == 1:
                return ValueError("Bad API response.")
            self.game_info_cache[game_id] = resp["data"][0]
            return resp["data"][0]

    async def get_user_info(self):
        """Get Twitch user info."""
        url = self.build_url("users")
        resp = await self.get_api_response(url)
        if not len(resp["data"]) == 1:
            return ValueError("Bad API response.")
        return resp["data"][0]

    @staticmethod
    def build_url(loc, params=None):
        """Construct API URL."""
        url_parts = list(urlparse(TWITCH_API_URL))
        url_parts[2] += loc
        if params:
            url_parts[4] = urlencode(params)
        return urlunparse(url_parts)

    async def get_api_response(self, url):
        """Perform API request."""
        attempts = 3
        attempt = 0
        while attempt < attempts:
            try:
                async with aiohttp.ClientSession() as session:
                    self._logger.debug(f"Request: {url}")
                    if self.api_thread.auth.token is None:
                        raise NotAuthorizedException
                    headers = {
                        "Client-ID": TWITCH_CLIENT_ID,
                        "Authorization": f"Bearer {self.api_thread.auth.token}",
                    }
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            self.api_thread.auth.token = None
                            raise NotAuthorizedException
                        else:
                            raise aiohttp.ClientConnectorError(
                                f"Unexpected status code: {response.status}"
                            )
            except NotAuthorizedException:
                self._logger.info("Not authorized")
                attempt += 1
                auth_event = asyncio.Event()
                GLib.idle_add(self.api_thread.app.not_authorized, auth_event)
                self._logger.debug("Waiting for authorization")
                await auth_event.wait()
