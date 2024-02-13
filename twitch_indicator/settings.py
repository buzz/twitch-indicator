import logging
from typing import TYPE_CHECKING, Optional

from gi.repository import Gio, GLib

from twitch_indicator.constants import SETTINGS_KEY
from twitch_indicator.state import ChannelState

if TYPE_CHECKING:
    from twitch_indicator.app import TwitchIndicatorApp


class Settings:
    def __init__(self, app: "TwitchIndicatorApp") -> None:
        self._app = app
        self._logger = logging.getLogger(__name__)
        self.settings = Gio.Settings.new(SETTINGS_KEY)

    def get_enabled_channel_ids(self) -> dict[int, ChannelState]:
        """Get and parse enabled channel IDs from settings."""
        enabled_str = self.get_string("enabled-channel-ids")
        enabled_channel_ids: dict[int, ChannelState] = {}
        try:
            for channel in enabled_str.split(","):
                channel_id, val = channel.split(":")
                enabled_channel_ids[int(channel_id)] = (
                    ChannelState.ENABLED if val == "1" else ChannelState.DISABLED
                )
        except ValueError:
            pass
        return enabled_channel_ids

    def get_boolean(self, key: str) -> bool:
        return self.settings.get_boolean(key)

    def set_boolean(self, key: str, value: bool) -> bool:
        return self.settings.set_boolean(key, value)

    def get_double(self, key: str) -> float:
        return self.settings.get_double(key)

    def set_double(self, key: str, value: float) -> bool:
        return self.settings.set_double(key, value)

    def get_int(self, key: str) -> int:
        return self.settings.get_int(key)

    def set_int(self, key: str, value: int) -> bool:
        return self.settings.set_int(key, value)

    def get_string(self, key: str) -> str:
        return self.settings.get_string(key)

    def set_string(self, key: str, value: str) -> bool:
        return self.settings.set_string(key, value)

    def get_default_value(self, key: str) -> Optional["GLib.Variant"]:
        return self.settings.get_default_value(key)

    def setup_event_handlers(self) -> None:
        self._app.state.add_handler("enabled_channel_ids", self._set_enabled_channel_ids)
        self.settings.connect("changed::refresh-interval", self._on_refresh_interval_changed)

    def _set_enabled_channel_ids(self, enabled_channel_ids: dict[str, ChannelState]) -> None:
        """Store serialized enabled channel IDs to settings."""
        enabled_list: list[str] = []
        with self._app.state.locks["enabled_channel_ids"]:
            for channel_id, enabled in enabled_channel_ids.items():
                enabled_list.append(f"{channel_id}:{enabled}")
        self.set_string("enabled-channel-ids", ",".join(enabled_list))

    def _on_refresh_interval_changed(self, settings: Gio.Settings, key: str) -> None:
        if self._app.api_manager.loop is not None:
            func = self._app.api_manager.update_refresh_interval
            self._app.api_manager.loop.call_soon_threadsafe(func, self.get_double(key))
