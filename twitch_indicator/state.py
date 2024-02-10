import asyncio
import inspect
import threading

from twitch_indicator.util import coro_exception_handler


class State:
    locks = {
        "user_info": threading.Lock(),
        "followed_channels": threading.Lock(),
        "live_streams": threading.Lock(),
        "enabled_channel_ids": threading.Lock(),
    }

    def __init__(self, app):
        self._app = app
        self._handlers = {}

        self.user_info = None
        self.followed_channels = []
        self.live_streams = []

        # Enabled channels (1=enabled, 2=realtime)
        self.enabled_channel_ids = self._app.settings.get_enabled_channel_ids()

    def set_user_info(self, user_info):
        self._set_value("user_info", user_info)

    def set_followed_channels(self, followed_channels):
        self._set_value("followed_channels", followed_channels)

    def set_live_streams(self, live_streams):
        self._set_value("live_streams", live_streams)

    def add_live_streams(self, added_streams):
        with self.locks["live_streams"]:
            for stream in added_streams:
                try:
                    idx = next(
                        i
                        for i, s in enumerate(self.live_streams)
                        if s["user_id"] == stream["user_id"]
                    )
                    self.live_streams[idx] = stream
                except StopIteration:
                    self.live_streams.append(stream)
        self._trigger_event("add_live_streams", added_streams)
        self._trigger_event("live_streams", self.live_streams)

    def remove_live_streams(self, user_ids):
        with self.locks["live_streams"]:
            self.live_streams = [
                s for s in self.live_streams if s["user_id"] not in user_ids
            ]
        self._trigger_event("live_streams", self.live_streams)

    def set_enabled_channel_ids(self, enabled_channel_ids):
        self._set_value("enabled_channel_ids", enabled_channel_ids)

    def add_handler(self, event, handler):
        """Register event handler."""
        if event in self._handlers:
            self._handlers[event].append(handler)
        else:
            self._handlers[event] = [handler]

    def remove_handler(self, event, handler):
        """Unregister event handler."""
        if event in self._handlers and handler in self._handlers[event]:
            self._handlers[event].remove(handler)

    def _trigger_event(self, event, *args, **kwargs):
        if event in self._handlers:
            for handler in self._handlers[event]:
                if inspect.iscoroutinefunction(handler):
                    coro = handler(*args, **kwargs)
                    fut = asyncio.run_coroutine_threadsafe(coro, self.api_manager.loop)
                    fut.add_done_callback(coro_exception_handler)
                else:
                    handler(*args, **kwargs)

    def _set_value(self, name, val):
        with self.locks[name]:
            setattr(self, name, val)
        self._trigger_event(name, val)
