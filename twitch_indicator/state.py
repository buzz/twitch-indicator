import asyncio
import inspect
import threading
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Optional

from twitch_indicator.api.models import FollowedChannel, Stream, User, ValidationInfo
from twitch_indicator.utils import coro_exception_handler

if TYPE_CHECKING:
    from twitch_indicator.app import TwitchIndicatorApp

Handler = Callable[[Any], None | Coroutine[None, None, None]]


class ChannelState(StrEnum):
    DISABLED = "0"
    ENABLED = "1"


class State:
    locks: dict[str, threading.Lock] = {
        "first_run": threading.Lock(),
        "validation_info": threading.Lock(),
        "user": threading.Lock(),
        "followed_channels": threading.Lock(),
        "live_streams": threading.Lock(),
        "enabled_channel_ids": threading.Lock(),
    }

    def __init__(self, app: "TwitchIndicatorApp") -> None:
        self._app = app
        self._handlers: dict[str, list[Handler]] = {}

        self.first_run = True
        self.validation_info: Optional[ValidationInfo] = None
        self.user: Optional[User] = None
        self.followed_channels: list[FollowedChannel] = []
        self.live_streams: list[Stream] = []
        self.enabled_channel_ids = self._app.settings.get_enabled_channel_ids()

    def reset(self):
        """Reset user state."""
        self.set_first_run(True)
        self.set_validation_info(None)
        self.set_user(None)
        self.set_followed_channels([])
        self.set_live_streams([])

    def set_first_run(self, first_run: bool) -> None:
        self._set_value("first_run", first_run)

    def set_validation_info(self, validation_info: Optional[ValidationInfo]) -> None:
        self._set_value("validation_info", validation_info)

    def set_user(self, user: Optional[User]) -> None:
        self._set_value("user", user)

    def set_followed_channels(self, followed_channels: list[FollowedChannel]) -> None:
        self._set_value("followed_channels", followed_channels)

    def set_live_streams(self, live_streams: list[Stream]) -> None:
        self._set_value("live_streams", live_streams)

    def set_enabled_channel_ids(self, enabled_channel_ids: dict[str, ChannelState]) -> None:
        self._set_value("enabled_channel_ids", enabled_channel_ids)

    def add_handler(self, name: str, handler: Handler) -> None:
        """Register event handler."""
        if name in self._handlers:
            self._handlers[name].append(handler)
        else:
            self._handlers[name] = [handler]

    def remove_handler(self, name: str, handler: Handler) -> None:
        """Unregister event handler."""
        if name in self._handlers and handler in self._handlers[name]:
            self._handlers[name].remove(handler)

    def _trigger_event(self, name: str, *args: list[Any], **kwargs: dict[str, Any]) -> None:
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
