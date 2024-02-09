import asyncio
import logging
import re
import time
from urllib.parse import urlencode, urlparse, urlunparse

import aiofiles
import aiohttp
from aiofiles.os import path
from gi.repository import GLib

from twitch_indicator.constants import (
    DEFAULT_AVATAR,
    TWITCH_API_URL,
    TWITCH_AUTH_URL,
    TWITCH_CLIENT_ID,
    TWITCH_PAGE_SIZE,
)
from twitch_indicator.errors import NotAuthorizedException
from twitch_indicator.util import get_image_filename


class TwitchApi:
    """Access Twitch API."""

    def __init__(self, api_thread):
        self._logger = logging.getLogger(__name__)
        self.api_thread = api_thread

    async def validate(self):
        """
        Validate token.

        https://dev.twitch.tv/docs/authentication/validate-tokens/
        """
        self._logger.debug("validate()")

        url = self._build_url("validate", url=TWITCH_AUTH_URL)
        resp = await self._get_api_response(url)

        return resp

    async def fetch_followed_channels(self, user_id):
        """
        Fetch followed channels and return as list of dictionaries.

        https://dev.twitch.tv/docs/api/reference/#get-followed-channels
        """
        self._logger.debug("fetch_followed_channels()")

        loc = "channels/followed"
        url = self._build_url(loc, {"user_id": user_id, "first": TWITCH_PAGE_SIZE})
        resp = await self._get_api_response(url)

        total = int(resp["total"])
        fetched = len(resp["data"])
        data = resp["data"]

        if total == 0:
            return []

        last = resp
        while fetched < total:
            url = self._build_url(
                loc,
                {
                    "after": last["pagination"]["cursor"],
                    "user_id": user_id,
                    "first": TWITCH_PAGE_SIZE,
                },
            )
            nxt = await self._get_api_response(url)

            fetched += len(nxt["data"])
            data += nxt["data"]
            last = nxt

        return data

    async def fetch_live_streams(self, user_id):
        """
        Fetch live streams and return as list of dictionaries.

        https://dev.twitch.tv/docs/api/reference/#get-followed-streams
        """
        self._logger.debug("fetch_live_channels()")

        loc = "streams/followed"
        url = self._build_url(loc, {"user_id": user_id, "first": TWITCH_PAGE_SIZE})
        resp = await self._get_api_response(url)

        fetched = len(resp["data"])
        data = resp["data"]

        if fetched == 0:
            return []

        last = resp
        while fetched == TWITCH_PAGE_SIZE:
            url = self._build_url(
                loc,
                {
                    "after": last["pagination"]["cursor"],
                    "user_id": user_id,
                    "first": TWITCH_PAGE_SIZE,
                },
            )
            nxt = await self._get_api_response(url)

            fetched = len(nxt["data"])
            data += nxt["data"]
            last = nxt

        return data

    async def fetch_profile_pictures(self, streams):
        """
        Download profile picture if current one is older than 3 days.

        https://dev.twitch.tv/docs/api/reference/#get-users
        """
        self._logger.debug("fetch_profile_pictures()")

        # Skip images newer than 3 days
        user_ids = []
        three_days = 3 * 24 * 60 * 60
        for user_id in [s["user_id"] for s in streams]:
            filename = get_image_filename(user_id)
            try:
                time_diff = time.time() - await path.getmtime(filename)
                if time_diff > three_days:
                    user_ids.append(user_id)
            except FileNotFoundError:
                user_ids.append(user_id)

        # Fetch profile image URLs
        profile_urls = {}
        idx = 0
        max = TWITCH_PAGE_SIZE
        while idx < len(user_ids):
            curr_user_ids = user_ids[idx:max]

            params = [("id", id) for id in curr_user_ids]
            url = self._build_url("users", params)
            resp = await self._get_api_response(url)

            for d in resp["data"]:
                profile_urls[d["id"]] = d["profile_image_url"]

            idx += len(curr_user_ids)
            max += TWITCH_PAGE_SIZE

        # Download images
        for user_id, profile_image_url in profile_urls.items():
            # Download 150x150 variant
            async with aiohttp.ClientSession() as session:
                url = re.sub(r"-\d+x\d+", "-150x150", profile_image_url)
                async with session.get(url) as response:
                    if response.status == 200:
                        # Save image
                        img_data = await response.read()
                        filename = get_image_filename(user_id)
                        async with aiofiles.open(filename, "wb") as f:
                            await f.write(img_data)
                            self._logger.debug(
                                f"fetch_profile_pictures(): Saved {filename}"
                            )

    @staticmethod
    def _build_url(path_append, params=None, url=TWITCH_API_URL):
        """Construct API URL."""
        url_parts = urlparse(url)
        url_parts = url_parts._replace(path=url_parts.path + path_append)
        if params:
            url_parts = url_parts._replace(query=urlencode(params))
        return urlunparse(url_parts)

    async def _get_api_response(self, url):
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
            except NotAuthorizedException:
                self._logger.info("_get_api_response(): Not authorized")
                attempt += 1
                auth_event = asyncio.Event()
                GLib.idle_add(self.api_thread.app.not_authorized, auth_event)
                await auth_event.wait()
