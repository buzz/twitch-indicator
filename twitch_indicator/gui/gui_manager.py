import asyncio
from typing import TYPE_CHECKING, Optional

from gi.repository import Gtk

from twitch_indicator.gui.dialogs.auth_dialog import AuthDialog
from twitch_indicator.gui.dialogs.settings_dialog import SettingsDialog
from twitch_indicator.gui.indicator import Indicator
from twitch_indicator.gui.notifications import Notifications

if TYPE_CHECKING:
    from twitch_indicator.app import TwitchIndicatorApp


class GuiManager:
    def __init__(self, app: "TwitchIndicatorApp") -> None:
        self.app = app
        self._indicator = Indicator(self)
        self._notifications = Notifications(self)
        self._auth_dialog: Optional[AuthDialog] = None
        self._settings_dialog: Optional[SettingsDialog] = None

    def run(self) -> None:
        """Run Gtk main loop."""
        Gtk.main()

    def quit(self) -> None:
        """Destroy windows and quit."""
        if self._auth_dialog is not None:
            self._auth_dialog.destroy()
        if self._settings_dialog is not None:
            self._settings_dialog.destroy()
        Gtk.main_quit()

    def show_settings(self) -> None:
        """Show settings dialog."""
        if self._settings_dialog:
            self._settings_dialog.present()
        else:
            self._settings_dialog = SettingsDialog(self)
            self._settings_dialog.run()
            self._settings_dialog = None

    def show_auth(self, auth_event: Optional[asyncio.Event]) -> None:
        """Show authentication dialog."""
        if self._auth_dialog is not None:
            self._auth_dialog.present()
        else:
            self._auth_dialog = AuthDialog(self, auth_event)
            self._auth_dialog.run()
            self._auth_dialog = None
