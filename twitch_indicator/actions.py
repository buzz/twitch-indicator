import logging
import subprocess
import webbrowser
from typing import TYPE_CHECKING, Callable, Optional, Union

from gi.repository import Gio, GLib

from twitch_indicator.utils import build_stream_url

if TYPE_CHECKING:
    from twitch_indicator.app import TwitchIndicatorApp


ActionCallback = Union[
    Callable[[Gio.SimpleAction, None], None],
    Callable[[Gio.SimpleAction, GLib.Variant], None],
]
ActionDef = tuple[str, Optional[GLib.VariantType], ActionCallback]


class Actions:
    def __init__(self, app: "TwitchIndicatorApp") -> None:
        self._logger = logging.getLogger(__name__)
        self._app: "TwitchIndicatorApp" = app
        self.action_group = Gio.SimpleActionGroup()
        self._setup_actions()

    def _setup_actions(self):
        actions: tuple[ActionDef, ...] = (
            ("quit", None, self._on_quit),
            ("settings", None, self._on_settings),
            ("open-stream", GLib.VariantType("s"), self._on_open_stream),
        )
        for name, param_type, cb in actions:
            action = Gio.SimpleAction.new(name, param_type)
            action.connect("activate", cb)
            self.action_group.add_action(action)

    def _on_quit(self, action: Gio.SimpleAction, param: None) -> None:
        """Callback for the quit action."""
        self._app.gui_manager.app.quit()

    def _on_settings(self, action: Gio.SimpleAction, param: None) -> None:
        """Callback for the settings action."""
        self._app.gui_manager.show_settings()

    def _on_open_stream(self, action: Gio.SimpleAction, param: GLib.Variant) -> None:
        """
        Callback for the open-stream action.

        Open URL in browser using either default webbrowser or custom command.
        """
        self._logger.debug("_on_open_stream(): %s", param)

        user_login = param.get_string()
        open_cmd = self._app.settings.get_string("open-command")
        url = build_stream_url(user_login)
        browser = webbrowser.get().basename
        formatted = open_cmd.format(url=url, browser=browser).split()
        subprocess.Popen(formatted)
