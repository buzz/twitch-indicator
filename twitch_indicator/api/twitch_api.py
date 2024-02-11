import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse, urlunparse

import aiofiles
import aiohttp
from aiofiles.os import path
from gi.repository import GLib

from twitch_indicator.api.exceptions import (
    NotAuthorizedException,
    RateLimitExceededException,
)
from twitch_indicator.constants import (
    TWITCH_API_URL,
    TWITCH_AUTH_URL,
    TWITCH_CLIENT_ID,
    TWITCH_PAGE_SIZE,
)
from twitch_indicator.util import get_cached_image_filename


class TwitchApi:
    """Access Twitch API."""

    def __init__(self, api_manager):
        self._logger = logging.getLogger(__name__)
        self._api_manager = api_manager

    async def validate(self):
        """
        Validate token.

        https://dev.twitch.tv/docs/authentication/validate-tokens/
        """
        self._logger.debug("validate()")

        url = self.build_url("validate", url=TWITCH_AUTH_URL)
        resp = await self.get_api_response(url)

        return resp

    async def fetch_followed_channels(self, user_id):
        """
        Fetch followed channels and return as list of dictionaries.

        https://dev.twitch.tv/docs/api/reference/#get-followed-channels
        """
        self._logger.debug("fetch_followed_channels()")

        loc = "channels/followed"
        url = self.build_url(loc, {"user_id": user_id, "first": TWITCH_PAGE_SIZE})
        resp = await self.get_api_response(url)

        total = int(resp["total"])
        fetched = len(resp["data"])
        data = resp["data"]

        if total == 0:
            return []

        last = resp
        while fetched < total:
            url = self.build_url(
                loc,
                {
                    "after": last["pagination"]["cursor"],
                    "user_id": user_id,
                    "first": TWITCH_PAGE_SIZE,
                },
            )
            nxt = await self.get_api_response(url)

            fetched += len(nxt["data"])
            data += nxt["data"]
            last = nxt

        return data

    async def fetch_followed_streams(self, user_id):
        """
        Fetch live streams followed by user_id and return as list of dictionaries.

        https://dev.twitch.tv/docs/api/reference/#get-followed-streams
        """
        self._logger.debug("fetch_followed_streams()")

        loc = "streams/followed"
        url = self.build_url(loc, {"user_id": user_id, "first": TWITCH_PAGE_SIZE})
        resp = await self.get_api_response(url)

        fetched = len(resp["data"])
        data = resp["data"]

        if fetched == 0:
            return []

        last = resp
        while fetched == TWITCH_PAGE_SIZE:
            params = {
                "after": last["pagination"]["cursor"],
                "user_id": user_id,
                "first": TWITCH_PAGE_SIZE,
            }
            url = self.build_url(loc, params)
            nxt = await self.get_api_response(url)

            fetched = len(nxt["data"])
            data += nxt["data"]
            last = nxt

        return data

    async def fetch_streams(self, user_ids):
        """
        Fetch live streams of user_ids and return as list of dictionaries.

        https://dev.twitch.tv/docs/api/reference/#get-streams
        """
        self._logger.debug("fetch_streams()")

        if len(user_ids) > TWITCH_PAGE_SIZE:
            msg = f"user_ids may only contain up to {TWITCH_PAGE_SIZE} entries"
            raise ValueError(msg)

        params = [("user_id", user_id) for user_id in user_ids]
        params.append(("first", TWITCH_PAGE_SIZE))
        url = self.build_url("streams", params)
        resp = await self.get_api_response(url)
        return resp["data"]

    async def fetch_profile_pictures(self, all_user_ids):
        """
        Download profile picture if current one is older than 3 days.

        https://dev.twitch.tv/docs/api/reference/#get-users
        """
        self._logger.debug("fetch_profile_pictures()")

        # Skip images newer than 3 days
        user_ids = []
        now = datetime.now(timezone.utc)
        for user_id in all_user_ids:
            filename = get_cached_image_filename(user_id)
            try:
                mtimestamp = datetime.utcfromtimestamp(await path.getmtime(filename))
                mtimestamp = mtimestamp.replace(tzinfo=timezone.utc)
                if now - mtimestamp > timedelta(days=3):
                    user_ids.append(user_id)
            except FileNotFoundError:
                user_ids.append(user_id)

        # Fetch profile image URLs
        profile_urls = {}
        idx = 0
        max = TWITCH_PAGE_SIZE
        while idx < len(user_ids):
            curr_user_ids = user_ids[idx:max]

            params = [("id", user_id) for user_id in curr_user_ids]
            url = self.build_url("users", params)
            resp = await self.get_api_response(url)

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
                        filename = get_cached_image_filename(user_id)
                        async with aiofiles.open(filename, "wb") as f:
                            await f.write(img_data)
                            self._logger.debug(
                                f"fetch_profile_pictures(): Saved {filename}"
                            )

    async def get_api_response(self, url, method="GET", json=None):
        """Perform API request."""
        attempts = 3
        attempt = 0
        headers = {
            "Client-Id": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {self._api_manager.auth.token}",
        }
        while attempt < attempts:
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    self._logger.debug(
                        f"get_api_response(): Attempt {attempt+1}/{attempts} {method} {url}"
                    )
                    if self._api_manager.auth.token is None:
                        raise NotAuthorizedException
                    async with session.request(method, url, json=json) as response:
                        if response.status in (200, 202, 204):
                            return await response.json()
                        elif response.status == 401:
                            raise NotAuthorizedException
                        elif response.status == 429:
                            raise RateLimitExceededException
                        else:
                            msg = f"Unhandled status code: {response.status}"
                            raise RuntimeError(msg)
            except NotAuthorizedException:
                self._logger.info("_get_api_response(): Not authorized")
                self._api_manager.auth.token = None
                auth_event = asyncio.Event()
                GLib.idle_add(self._api_manager.app.not_authorized, auth_event)
                # Wait for auth flow to finish
                await auth_event.wait()
            finally:
                attempt += 1

    @staticmethod
    def build_url(path_append, params=None, url=TWITCH_API_URL):
        """Construct API URL."""
        url_parts = urlparse(url)
        url_parts = url_parts._replace(path=url_parts.path + path_append)
        if params:
            url_parts = url_parts._replace(query=urlencode(params))
        return urlunparse(url_parts)
