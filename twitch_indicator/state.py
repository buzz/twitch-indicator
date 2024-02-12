import asyncio
import inspect
import threading
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Callable, Optional

from twitch_indicator.api.models import FollowedChannel, Stream, UserInfo
from twitch_indicator.utils import coro_exception_handler

if TYPE_CHECKING:
    from twitch_indicator.app import TwitchIndicatorApp


class ChannelState(StrEnum):
    DISABLED = "0"
    ENABLED = "1"


class State:
    locks: dict[str, threading.Lock] = {
        "first_run": threading.Lock(),
        "user_info": threading.Lock(),
        "followed_channels": threading.Lock(),
        "live_streams": threading.Lock(),
        "enabled_channel_ids": threading.Lock(),
    }

    def __init__(self, app: "TwitchIndicatorApp") -> None:
        self._app = app
        self._handlers: dict[str, list[Callable[[Any], None]]] = {}

        self.first_run = True
        self.user_info: Optional[UserInfo] = None
        self.followed_channels: list[FollowedChannel] = []
        self.live_streams: list[Stream] = []
        self.enabled_channel_ids = self._app.settings.get_enabled_channel_ids()

    def set_first_run(self, first_run: bool) -> None:
        self._set_value("first_run", first_run)

    def set_user_info(self, user_info: Optional[UserInfo]) -> None:
        self._set_value("user_info", user_info)

    def set_followed_channels(self, followed_channels: list[FollowedChannel]) -> None:
        self._set_value("followed_channels", followed_channels)

    def set_live_streams(self, live_streams: list[Stream]) -> None:
        self._set_value("live_streams", live_streams)

    def set_enabled_channel_ids(
        self, enabled_channel_ids: dict[str, ChannelState]
    ) -> None:
        self._set_value("enabled_channel_ids", enabled_channel_ids)

    def add_handler(self, name: str, handler: Callable[[Any], None]) -> None:
        """Register event handler."""
        if name in self._handlers:
            self._handlers[name].append(handler)
        else:
            self._handlers[name] = [handler]

    def remove_handler(self, name: str, handler: Callable[[Any], None]) -> None:
        """Unregister event handler."""
        if name in self._handlers and handler in self._handlers[name]:
            self._handlers[name].remove(handler)

    def _trigger_event(
        self, name: str, *args: list[Any], **kwargs: dict[str, Any]
    ) -> None:
        if name in self._handlers:
            for handler in self._handlers[name]:
                if inspect.iscoroutinefunction(handler):
                    loop = self._app.api_manager.loop
                    if loop is not None:
                        coro = handler(*args, **kwargs)
                        fut = asyncio.run_coroutine_threadsafe(coro, loop)
                        fut.add_done_callback(coro_exception_handler)
                else:
                    handler(*args, **kwargs)

    def _set_value(self, name: str, val: Any) -> None:
        with self.locks[name]:
            setattr(self, name, val)
        self._trigger_event(name, val)
