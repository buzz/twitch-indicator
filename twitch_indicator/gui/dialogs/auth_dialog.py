import asyncio
from typing import TYPE_CHECKING, Optional, cast

from gi.repository import GdkPixbuf, GLib, Gtk

from twitch_indicator.constants import TWITCH_LOGO_FILENAME
from twitch_indicator.gui.dialogs.base import BaseDialog
from twitch_indicator.utils import get_data_file

if TYPE_CHECKING:
    from twitch_indicator.gui.gui_manager import GuiManager


class AuthDialog(BaseDialog[Gtk.Dialog]):
    def __init__(self, gui_manager: "GuiManager", auth_event: Optional[asyncio.Event]) -> None:
        super().__init__("auth", gui_manager)
        self._auth_event = auth_event
        self._img_twitch = cast(Gtk.Image, self._builder.get_object("img_twitch"))

    def run(self) -> None:
        filepath = get_data_file(TWITCH_LOGO_FILENAME)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(filepath))
        self._img_twitch.set_from_pixbuf(pixbuf)
        self._dialog.show_all()

        try:
            if self._dialog.run() == Gtk.ResponseType.OK:
                GLib.idle_add(self._gui_manager.app.login, self._auth_event)
            else:
                GLib.idle_add(self._gui_manager.app.quit)

        finally:
            self._dialog.destroy()
