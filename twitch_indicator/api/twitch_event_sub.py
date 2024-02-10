import logging
from datetime import datetime, timedelta, timezone
from json import JSONDecodeError

import aiohttp
from gi.repository import GLib

from twitch_indicator.api.exceptions import RateLimitExceededException
from twitch_indicator.api.twitch_api import TwitchApi
from twitch_indicator.constants import (
    TWITCH_MAX_SUBSCRIPTIONS,
    TWITCH_WS_KEEPALIVE_TIMEOUT,
    TWITCH_WS_URL,
)
from twitch_indicator.util import parse_rfc3339_timestamp


class TwitchEventSub:
    def __init__(self, api_manager):
        self._logger = logging.getLogger(__name__)
        self._api_manager = api_manager
        self._api = api_manager.api
        self._handled_msg_ids = []
        self._last_msg_dt = 0

    async def start_listening(self):
        """Subscribe to events."""

        async with aiohttp.ClientSession() as session:
            params = {"keepalive_timeout_seconds": TWITCH_WS_KEEPALIVE_TIMEOUT}
            async with session.ws_connect(TWITCH_WS_URL, params=params) as ws:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = msg.json()
                            self._logger.debug(f"_handle_message(): JSON {data}")
                            await self._handle_message(data)
                        except JSONDecodeError:
                            self._logger.debug(f"_handle_message(): TEXT {msg.data}")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        self._logger.error(f"_handle_message(): ERROR {msg}")

    async def _handle_message(self, msg):
        """Handle websocket message."""

        # Remember last message timestamp
        now = datetime.now(timezone.utc)
        self._last_msg_dt = now

        # Extract metadata
        try:
            msg_id = msg["metadata"]["message_id"]
            message_type = msg["metadata"]["message_type"]
            timestamp = parse_rfc3339_timestamp(msg["metadata"]["message_timestamp"])
        except ValueError:
            msg = f"_handle_message(): Failed to parse message timestamp: {msg}"
            self._logger.warn(msg)
            return
        except KeyError:
            self._logger.warn(f"_handle_message(): Failed to parse message: {msg}")
            return

        # Skip duplicate events
        # https://dev.twitch.tv/docs/eventsub/#handling-duplicate-events
        try:
            self._record_msg_id(msg_id)
        except ValueError:
            self._logger.debug(
                f"_handle_twitch_message(): Discarding duplicate event: {msg}"
            )
            return

        # Guard against replay attacks
        # https://dev.twitch.tv/docs/eventsub/#guarding-against-replay-attacks
        if now - timestamp > timedelta(minutes=10):
            self._logger.warn(
                f"_handle_twitch_message(): Received old message. Discarding...: {msg}"
            )
            return

        if message_type == "session_keepalive":
            self._logger.debug("_handle_twitch_message(): session_keepalive")
            return

        if message_type == "notification":
            self._logger.debug("_handle_twitch_message(): notification")
            await self._handle_notification(msg)
            return

        if message_type == "session_welcome":
            self._logger.debug("_handle_twitch_message(): session_welcome")
            try:
                if msg["payload"]["session"]["status"] == "connected":
                    self._session_id = msg["payload"]["session"]["id"]
                    await self._setup_subscriptions()
            except KeyError:
                self._logger.warn(f"Failed to parse session ID: {msg}")
            return

        if message_type == "session_reconnect":
            self._logger.debug(f"_handle_twitch_message(): session_reconnect: {msg}")
            # TODO
            return

        if message_type == "revocation":
            self._logger.debug(f"_handle_twitch_message(): revocation: {msg}")
            # TODO
            return

    async def _setup_subscriptions(self):
        self._logger.debug("_setup_subscriptions()")

        # Get enabled channel IDs
        with self._api_manager.app.state.locks["enabled_channel_ids"]:
            items = self._api_manager.app.state.enabled_channel_ids.items()
            realtime_channel_ids = [user_id for user_id, mode in items if mode == "2"]

        if realtime_channel_ids > TWITCH_MAX_SUBSCRIPTIONS:
            realtime_channel_ids = realtime_channel_ids[:TWITCH_MAX_SUBSCRIPTIONS]

        # Get current live streams
        with self._api_manager.app.state.locks["live_streams"]:
            live_channel_ids = [
                s["user_id"] for s in self._api_manager.app.state.live_streams
            ]

        for user_id in realtime_channel_ids:
            sub_type = (
                "stream.offline" if user_id in live_channel_ids else "stream.online"
            )
            try:
                await self._subscribe(sub_type, user_id)
            except RateLimitExceededException:
                msg = "_setup_subscriptions(): Max. subscriptions reached"
                self._logger.warn(msg)
                break

    async def _subscribe(self, sub_type, user_id):
        self._logger.debug(f"_subscribe(): user_id={user_id} sub_type={sub_type}")

        payload = {
            "type": sub_type,
            "version": "1",
            "condition": {
                "broadcaster_user_id": user_id,
            },
            "transport": {
                "method": "websocket",
                "session_id": self._session_id,
            },
        }
        url = TwitchApi.build_url("eventsub/subscriptions")
        response = await self._api.get_api_response(url, method="POST", json=payload)
        self._logger.debug(f"_setup_subscriptions(): response={response}")

        if response["data"][0]["status"] != "enabled":
            raise RuntimeError("Failed to enable subscription")

    async def _unsubscribe(self, sub_id):
        self._logger.debug(f"_unsubscribe(): sub_id={sub_id}")

        url = TwitchApi.build_url("eventsub/subscriptions", params={"id": sub_id})
        await self._api.get_api_response(url, method="DELETE")

    async def _handle_notification(self, msg):
        self._logger.debug("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        self._logger.debug(f"_handle_notification() msg={msg}")
        self._logger.debug("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

        # Extract subscription info
        try:
            sub_id = msg["payload"]["subscription"]["id"]
            sub_type = msg["payload"]["subscription"]["type"]
        except KeyError:
            msg = f"_handle_notification(): Unable to extract subscription info: {msg}"
            self._logger.debug(msg)
            return

        if sub_type in ("stream.online", "stream.offline"):
            try:
                user_id = msg["payload"]["event"]["broadcaster_user_id"]
            except KeyError:
                msg = f"_handle_notification(): Unable to extract broadcaster_user_id: {msg}"
                self._logger.debug(msg)
                return

            # Update app state
            if sub_type == "stream.online":
                await self._api.fetch_profile_pictures([user_id])
                streams = await self._api.fetch_streams([user_id])
                GLib.idle_add(self._api_manager.app.state.add_live_streams, streams)
            else:
                func = self._api_manager.app.state.remove_live_streams
                GLib.idle_add(func, [user_id])

            # Delete old subscription (online<->offline)
            await self._unsubscribe(sub_id)

            # Add new subscription (online<->offline)
            try:
                if sub_type == "stream.online":
                    await self._subscribe("stream.offline", user_id)
                else:
                    await self._subscribe("stream.online", user_id)
            except RuntimeError:
                msg = "_setup_subscriptions(): Failed to enable subscription"
                self._logger.error(msg)

    def _record_msg_id(self, msg_id):
        """Remember previous event IDs."""
        if msg_id in self._handled_msg_ids:
            raise ValueError()
        else:
            self._handled_msg_ids.append(msg_id)
        while len(self._handled_msg_ids) > 100:
            self._handled_msg_ids.pop()
