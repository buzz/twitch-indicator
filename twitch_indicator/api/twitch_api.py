import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import aiofiles
import aiohttp
from aiofiles.os import path
from gi.repository import GLib
from pydantic import TypeAdapter

from twitch_indicator.api.exceptions import (
    NotAuthorizedException,
    RateLimitExceededException,
)
from twitch_indicator.api.models import FollowedChannel, Stream, UserInfo
from twitch_indicator.constants import (
    TWITCH_AUTH_URL,
    TWITCH_CLIENT_ID,
    TWITCH_PAGE_SIZE,
)
from twitch_indicator.utils import Params, build_api_url, get_cached_image_filename

ta_followed_channels = TypeAdapter(list[FollowedChannel])
ta_streams = TypeAdapter(list[Stream])


class TwitchApi:
    """Access Twitch API."""

    def __init__(self, api_manager) -> None:
        self._logger = logging.getLogger(__name__)
        self._api_manager = api_manager

    async def validate(self) -> UserInfo:
        """
        Validate token.

        https://dev.twitch.tv/docs/authentication/validate-tokens/
        """
        self._logger.debug("validate()")

        url = build_api_url("validate", url=TWITCH_AUTH_URL)
        resp = await self._get_api_response(url)

        return UserInfo(**resp)

    async def fetch_followed_channels(self, user_id: int) -> list[FollowedChannel]:
        """
        Fetch followed channels and return as list of dictionaries.

        https://dev.twitch.tv/docs/api/reference/#get-followed-channels
        """
        self._logger.debug("fetch_followed_channels()")

        resp = await self._get_paginated_api_response("channels/followed", {"user_id": user_id})

        return ta_followed_channels.validate_python(resp)

    async def fetch_followed_streams(self, user_id: int) -> list[Stream]:
        """
        Fetch live streams followed by user_id and return as list of dictionaries.

        https://dev.twitch.tv/docs/api/reference/#get-followed-streams
        """
        self._logger.debug("fetch_followed_streams()")

        resp = await self._get_paginated_api_response("streams/followed", {"user_id": user_id})

        return ta_streams.validate_python(resp)

    async def fetch_profile_pictures(self, all_user_ids: Iterable[int]) -> None:
        """
        Download profile picture if current one is older than 3 days.

        https://dev.twitch.tv/docs/api/reference/#get-users
        """
        self._logger.debug("fetch_profile_pictures()")

        # Skip images newer than 3 days
        user_ids: list[int] = []
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
        profile_urls: dict[int, str] = {}
        idx = 0
        max = TWITCH_PAGE_SIZE
        while idx < len(user_ids):
            curr_user_ids = user_ids[idx:max]

            params = {"id": [user_id for user_id in curr_user_ids]}
            url = build_api_url("users", params)
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
                    if response.status != 200:
                        msg = f"Unable to download profile image: {url}"
                        self._logger.warning(msg)
                        continue

                    # Save image
                    img_data = await response.read()
                    filename = get_cached_image_filename(user_id)
                    async with aiofiles.open(filename, "wb") as f:
                        await f.write(img_data)
                        msg = "fetch_profile_pictures(): Saved %s"
                        self._logger.debug(msg, filename)

    async def _get_paginated_api_response(self, path: str, params_orig: Params) -> list[Any]:
        """Perform a series of requests for a paginated endpoint."""
        data: list[Any] = []
        cursor: Optional[str] = None
        params: Params = {**params_orig, "first": TWITCH_PAGE_SIZE}

        while True:
            if cursor is not None:
                params = {**params, "after": cursor}

            url = build_api_url(path, params)
            resp = await self._get_api_response(url)
            data += resp["data"]

            try:
                cursor = resp["pagination"]["cursor"]
            except KeyError:
                cursor = None

            if cursor is None:
                return data

    async def _get_api_response(
        self, url: str, method: str = "GET", json: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Perform API request."""
        attempts = 3
        attempt = 0
        while attempt < attempts:
            try:
                async with aiohttp.ClientSession() as session:
                    self._logger.debug(
                        f"get_api_response(): Attempt {attempt+1}/{attempts} {method} {url}"
                    )
                    if self._api_manager.auth.token is None:
                        raise NotAuthorizedException
                    headers = {
                        "Client-Id": TWITCH_CLIENT_ID,
                        "Authorization": f"Bearer {self._api_manager.auth.token}",
                    }
                    async with session.request(method, url, json=json, headers=headers) as response:
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

        raise RuntimeError("Unable to query API")
