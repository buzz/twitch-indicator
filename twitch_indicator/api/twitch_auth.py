import asyncio
import logging
import webbrowser
from os import chmod
from random import SystemRandom
from typing import Optional
from urllib.parse import urlparse, urlunparse

import aiofiles
from aiofiles.os import path
from aiohttp import web

from twitch_indicator.constants import (
    AUTH_TOKEN_PATH,
    TWITCH_AUTH_REDIRECT_URI,
    TWITCH_AUTH_SCOPES,
    TWITCH_AUTH_URL,
    TWITCH_CLIENT_ID,
    UNICODE_ASCII_CHARACTER_SET,
)
from twitch_indicator.utils import build_api_url, get_data_filepath


class Auth:
    """
    Handle API authentication using implicit grant flow.

    https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#implicit-grant-flow
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self.token: Optional[str] = None
        self._token_acquired_event: Optional[asyncio.Event] = None
        self._state: Optional[str] = None

    async def acquire_token(self, auth_event: asyncio.Event) -> None:
        """Start Twitch API user token flow."""
        self._logger.debug("acquire_token()")

        self._token_acquired_event = asyncio.Event()
        auth_url, self._state = self._build_auth_url()

        # Start local web server
        web_app = web.Application()
        routes = (
            web.get("/", self._handle_request),
            web.get("/success", self._handle_request_success),
        )
        web_app.add_routes(routes)
        runner = web.AppRunner(web_app)
        await runner.setup()
        redirect_uri_parts = urlparse(TWITCH_AUTH_REDIRECT_URI)
        site = web.TCPSite(runner, redirect_uri_parts.hostname, redirect_uri_parts.port)
        await site.start()
        self._logger.info("acquire_token(): Started OAuth webserver")

        # Open Twich auth URL
        webbrowser.open_new_tab(auth_url)
        await self._token_acquired_event.wait()
        self._token_acquired_event = None
        self._state = None
        await runner.shutdown()
        await runner.cleanup()
        self._logger.info("acquire_token(): Stopped OAuth webserver")

        auth_event.set()

    async def _handle_request(self, request: web.Request) -> web.Response:
        """
        Twitch auth redirect endpoint.

        Parse hash parameters and redirect to success page using JavaScript.
        The parameters are added as query string.
        """
        self._logger.debug("_handle_request()")

        success_url_parts = urlparse(TWITCH_AUTH_REDIRECT_URI)
        success_url_parts = success_url_parts._replace(path="/success")
        success_url = urlunparse(success_url_parts)

        filepath = get_data_filepath("auth_response.html")
        async with aiofiles.open(filepath, "r", encoding="UTF-8") as f:
            text = (await f.read()).replace("__SUCCESS_URL__", success_url)

        return web.Response(text=text, content_type="text/html")

    async def _handle_request_success(self, request: web.Request) -> web.Response:
        """
        Twitch auth success endpoint.

        Parse query parameters and show user success message.
        """
        self._logger.debug("_handle_request_success() url=%s", request.url)

        try:
            query = request.rel_url.query

            # Check response
            if query.get("token_type") != "bearer":
                raise ValueError("Wrong token type")
            if query.get("state") != self._state:
                raise ValueError("State value mismatch")

            self.token = query.get("access_token")
            if self.token is None:
                raise ValueError("No token received")

            await self._store_token(self.token)

            filepath = get_data_filepath("auth_success_response.html")
            async with aiofiles.open(filepath, "r", encoding="UTF-8") as f:
                return web.Response(text=await f.read(), content_type="text/html")
        except ValueError:
            return web.Response(status=401)
        finally:
            if self._token_acquired_event is not None:
                self._token_acquired_event.set()

    async def restore_token(self) -> None:
        """Restore auth token from config dir."""
        if await path.isfile(AUTH_TOKEN_PATH):
            async with aiofiles.open(AUTH_TOKEN_PATH, "r", encoding="UTF-8") as f:
                self.token = await f.read()

    async def _store_token(self, token: str) -> None:
        """Store auth token to config dir."""
        async with aiofiles.open(AUTH_TOKEN_PATH, "w", encoding="UTF-8") as f:
            await f.write(token)
        chmod(AUTH_TOKEN_PATH, 0o600)

    @staticmethod
    def _build_auth_url() -> tuple[str, str]:
        rand = SystemRandom()
        state = "".join(rand.choice(UNICODE_ASCII_CHARACTER_SET) for x in range(30))
        params = {
            "client_id": TWITCH_CLIENT_ID,
            "force_verify": "false",
            "redirect_uri": TWITCH_AUTH_REDIRECT_URI,
            "response_type": "token",
            "scope": " ".join(TWITCH_AUTH_SCOPES),
            "state": state,
        }
        return build_api_url("authorize", params, url=TWITCH_AUTH_URL), state
