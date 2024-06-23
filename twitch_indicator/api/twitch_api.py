import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Iterable, Optional, TypeVar

import aiofiles
import aiohttp
from aiofiles.os import path
from gi.repository import GdkPixbuf, GLib
from pydantic import BaseModel

from twitch_indicator.api.exceptions import (
    NotAuthorizedException,
    RateLimitExceededException,
)
from twitch_indicator.api.models import (
    FollowedChannel,
    ListData,
    PaginatedResponse,
    Stream,
    User,
    ValidationInfo,
)
from twitch_indicator.constants import (
    TWITCH_AUTH_URL,
    TWITCH_CLIENT_ID,
    TWITCH_PAGE_SIZE,
)
from twitch_indicator.utils import Params, build_api_url, get_cached_image_filename

if TYPE_CHECKING:
    from twitch_indicator.api.api_manager import ApiManager

ModelT = TypeVar("ModelT", bound=BaseModel)


class TwitchApi:
    """Access Twitch API."""

    def __init__(self, api_manager: "ApiManager") -> None:
        self._logger = logging.getLogger(__name__)
        self._api_manager = api_manager
        self._session: Optional[aiohttp.ClientSession]

    def set_session(self, session: aiohttp.ClientSession) -> None:
        """Set client session."""
        self._session = session

    async def close_session(self) -> None:
        """Close client session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def validate(self) -> ValidationInfo:
        """
        Validate token.

        https://dev.twitch.tv/docs/authentication/validate-tokens/
        """
        self._logger.debug("validate()")

        url = build_api_url("validate", url=TWITCH_AUTH_URL)
        return ValidationInfo.model_validate_json(await self._get_api_response(url))

    async def fetch_followed_channels(self, user_id: int) -> list[FollowedChannel]:
        """
        Fetch followed channels and return as list of dictionaries.

        https://dev.twitch.tv/docs/api/reference/#get-followed-channels
        """
        self._logger.debug("fetch_followed_channels()")

        params = {"user_id": user_id}
        return await self._get_paginated_api_response(FollowedChannel, "channels/followed", params)

    async def fetch_followed_streams(self, user_id: int) -> list[Stream]:
        """
        Fetch live streams followed by user_id and return as list of dictionaries.

        https://dev.twitch.tv/docs/api/reference/#get-followed-streams
        """
        self._logger.debug("fetch_followed_streams()")

        params = {"user_id": user_id}
        return await self._get_paginated_api_response(Stream, "streams/followed", params)

    async def fetch_users(self, user_ids: list[int]) -> list[User]:
        """
        Download user info.

        https://dev.twitch.tv/docs/api/reference/#get-users
        """
        self._logger.debug("fetch_users(): %s", user_ids)

        url = build_api_url("users", {"id": user_ids})
        return self._parse_list_data_response(User, await self._get_api_response(url))

    async def fetch_profile_pictures(self, all_user_ids: Iterable[int]) -> None:
        """Download profile picture if current one is older than 3 days."""
        self._logger.debug("fetch_profile_pictures()")

        # Skip images newer than 3 days
        user_ids: list[int] = []
        now = datetime.now(timezone.utc)
        for user_id in all_user_ids:
            filename = get_cached_image_filename(user_id)
            filename_icon = get_cached_image_filename(user_id, "icon")
            try:
                # check regular variant
                mtimestamp = datetime.utcfromtimestamp(await path.getmtime(filename))
                mtimestamp = mtimestamp.replace(tzinfo=timezone.utc)
                if now - mtimestamp > timedelta(days=3):
                    user_ids.append(user_id)

                # check icon variant
                if not await path.isfile(filename_icon):
                    user_ids.append(user_id)
            except FileNotFoundError:
                user_ids.append(user_id)

        # Fetch profile image URLs
        profile_urls: dict[int, str] = {}
        idx = 0
        max = TWITCH_PAGE_SIZE
        while idx < len(user_ids):
            curr_user_ids = user_ids[idx:max]

            users = await self.fetch_users(curr_user_ids)
            profile_urls.update((u.id, u.profile_image_url) for u in users)

            idx += len(curr_user_ids)
            max += TWITCH_PAGE_SIZE

        await asyncio.gather(
            *(self._process_profile_url(user_id, url) for user_id, url in profile_urls.items())
        )

    async def _process_profile_url(self, user_id: int, profile_image_url: str) -> bool:
        """Download 150x150px variant profile image."""
        url = re.sub(r"-\d+x\d+", "-150x150", profile_image_url)
        if self._session is None:
            raise RuntimeError("No session object")
        async with self._session.get(url) as response:
            if response.status != 200:
                msg = f"_process_profile_url: Unable to download profile image: {url}"
                self._logger.warning(msg)
                return False
            img_data = await response.read()

        # scale image
        if self._api_manager.loop is not None:
            icon_img_data = await self._api_manager.loop.run_in_executor(
                None, self._scale_img, img_data, user_id, url
            )

        # Save image
        filename = get_cached_image_filename(user_id)
        async with aiofiles.open(filename, "wb") as f:
            await f.write(img_data)
            msg = "fetch_profile_pictures(): Saved %s (regular)"
            self._logger.debug(msg, filename)
        filename_icon = get_cached_image_filename(user_id, "icon")
        async with aiofiles.open(filename_icon, "wb") as f:
            await f.write(icon_img_data)
            msg = "fetch_profile_pictures(): Saved %s (icon)"
            self._logger.debug(msg, filename_icon)

        return True

    def _scale_img(self, img_data: bytes, user_id: int, url: str) -> bytes:
        """Create PNG icon from profile image."""
        loader = GdkPixbuf.PixbufLoader.new()
        # Parse image data
        if not loader.write(img_data):
            msg = f"_process_profile_url(): Failed to parse image: url={url} user_id={user_id}"
            raise RuntimeError(msg)
        if not loader.close():
            msg = f"_process_profile_url(): Failed to finalize image loader: url={url} user_id={user_id}"
            raise RuntimeError(msg)
        pixbuf = loader.get_pixbuf()
        if pixbuf is None:
            msg = f"_process_profile_url(): Failed to get pixbuf: url={url} user_id={user_id}"
            raise RuntimeError(msg)
        if not loader.close():
            self._logger.warning("_process_profile_url(): Failed to close PixbufLoader")

        # create icon variant
        pixbuf_icon = pixbuf.scale_simple(32, 32, GdkPixbuf.InterpType.BILINEAR)
        if pixbuf_icon is None:
            msg = f"_process_profile_url(): Failed to scale pixbuf: url={url} user_id={user_id}"
            raise RuntimeError()

        # Create PNG data
        res, png_data = pixbuf_icon.save_to_bufferv("png")
        if not res:
            msg = f"_process_profile_url(): Failed to create PNG from pixbuf: url={url} user_id={user_id}"
            raise RuntimeError(msg)

        return png_data

    async def _get_paginated_api_response(
        self, model: type[ModelT], path: str, params: Params
    ) -> list[ModelT]:
        """Perform a series of requests for a paginated endpoint."""
        data: list[ModelT] = []
        cursor: Optional[str] = None
        req_params: Params = {**params, "first": TWITCH_PAGE_SIZE}

        while True:
            if cursor is not None:
                req_params = {**req_params, "after": cursor}

            url = build_api_url(path, req_params)
            response_text = await self._get_api_response(url)
            page_data, cursor = self._parse_paginated_response(model, response_text)
            data += page_data

            if cursor is None:
                return data

    async def _get_api_response(
        self, url: str, method: str = "GET", json: Optional[dict[str, Any]] = None
    ) -> str:
        """Perform API request."""
        if self._session is None:
            raise RuntimeError("No session object")

        attempts = 3
        attempt = 0
        while attempt < attempts:
            try:
                self._logger.debug(
                    f"get_api_response(): Attempt {attempt+1}/{attempts} {method} {url}"
                )
                if self._api_manager.auth.token is None:
                    raise NotAuthorizedException
                headers = {
                    "Client-Id": TWITCH_CLIENT_ID,
                    "Authorization": f"Bearer {self._api_manager.auth.token}",
                }
                async with self._session.request(
                    method, url, json=json, headers=headers
                ) as response:
                    if response.status in (200, 202, 204):
                        return await response.text()
                    elif response.status == 401:
                        raise NotAuthorizedException
                    elif response.status == 429:
                        raise RateLimitExceededException
                    else:
                        msg = f"Unhandled status code: {response.status}"
                        raise RuntimeError(msg)
            except NotAuthorizedException:
                self._logger.info("_get_api_response(): Not authorized")
                GLib.idle_add(self._api_manager.app.logout)
                auth_event = asyncio.Event()
                GLib.idle_add(self._api_manager.app.gui_manager.show_auth, auth_event)
                # Wait for auth flow to finish
                await auth_event.wait()
            finally:
                attempt += 1

        raise RuntimeError("Unable to query API")

    @staticmethod
    def _parse_list_data_response(model: type[ModelT], text: str) -> list[ModelT]:
        list_model: ListData[ModelT]
        if not TYPE_CHECKING:
            # Pydantic needs concrete type at runtime, but mypy wouldn't like this
            list_model = ListData[model]

        return list_model.model_validate_json(text).data

    @staticmethod
    def _parse_paginated_response(
        model: type[ModelT], text: str
    ) -> tuple[list[ModelT], str | None]:
        paginated_model: PaginatedResponse[ModelT]
        if not TYPE_CHECKING:
            # Pydantic needs concrete type at runtime, but mypy wouldn't like this
            paginated_model = PaginatedResponse[model]

        validated_model = paginated_model.model_validate_json(text)
        return validated_model.data, validated_model.pagination.cursor
