import logging

from gi.repository import Gio

from twitch_indicator.constants import SETTINGS_KEY


class Settings:
    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._app = app
        self._logger = logging.getLogger(__name__)
        self._settings = Gio.Settings.new(SETTINGS_KEY)

    def get_enabled_channel_ids(self):
        """Get and parse enabled channel IDs from settings."""
        enabled_str = self.get_string("enabled-channel-ids")
        enabled_channel_ids = {}
        try:
            for channel in enabled_str.split(","):
                channel_id, mode = channel.split(":")
                enabled_channel_ids[channel_id] = mode
        except ValueError:
            pass
        return enabled_channel_ids

    def get_boolean(self, *args, **kwargs):
        return self._settings.get_boolean(*args, **kwargs)

    def set_boolean(self, *args, **kwargs):
        return self._settings.set_boolean(*args, **kwargs)

    def get_int(self, *args, **kwargs):
        return self._settings.get_int(*args, **kwargs)

    def set_int(self, *args, **kwargs):
        return self._settings.set_int(*args, **kwargs)

    def get_string(self, *args, **kwargs):
        return self._settings.get_string(*args, **kwargs)

    def set_string(self, *args, **kwargs):
        return self._settings.set_string(*args, **kwargs)

    def setup_event_handler(self):
        self._app.state.add_handler(
            "enabled_channel_ids", self._set_enabled_channel_ids
        )

    def _set_enabled_channel_ids(self, enabled_channel_ids):
        """Store serialized enabled channel IDs to settings."""
        enabled_list = []
        with self._app.state.locks["enabled_channel_ids"]:
            for channel_id, mode in enabled_channel_ids.items():
                enabled_list.append(f"{channel_id}:{mode}")
            val = ",".join(enabled_list)

        self.set_string("enabled-channel-ids", val)
