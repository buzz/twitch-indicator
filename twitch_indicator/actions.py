import logging

from gi.repository import Gio, GLib

from twitch_indicator.utils import build_stream_url, open_stream


class Actions:
    def __init__(self, app):
        self._logger = logging.getLogger(__name__)
        self._app = app
        self.action_group = Gio.SimpleActionGroup()

        actions = (
            ("quit", None, self._on_quit),
            ("settings", None, self._on_settings),
            ("open-stream", GLib.VariantType("s"), self._on_open_stream),
        )
        for name, param_type, cb in actions:
            action = Gio.SimpleAction.new(name, param_type)
            action.connect("activate", cb)
            self.action_group.add_action(action)

    def _on_quit(self, action, param):
        """Callback for the quit action."""
        self._app.gui_manager.app.quit()

    def _on_settings(self, action, param):
        """Callback for the settings action."""
        self._app.gui_manager.show_settings()

    def _on_open_stream(self, action, user_login):
        """Callback for the open-stream action."""
        self._logger.debug(f"_on_open_stream(): {user_login}")
        open_cmd = self._app.settings.get_string("open-command")
        open_stream(build_stream_url(user_login.get_string()), open_cmd)
