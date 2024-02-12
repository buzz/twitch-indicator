import asyncio
from typing import TYPE_CHECKING, Optional

from gi.repository import GLib, Gtk

if TYPE_CHECKING:
    from twitch_indicator.gui.gui_manager import GuiManager


class AuthDialog:
    def __init__(self, gui_manager: "GuiManager") -> None:
        self._gui_manager = gui_manager
        self._dialog: Optional[Gtk.Dialog] = None

    def show(self, auth_event: "asyncio.Event") -> None:
        self._dialog = Gtk.Dialog(title="Twitch authentication")
        self._dialog.add_button(Gtk.STOCK_QUIT, Gtk.ResponseType.CANCEL)
        self._dialog.add_button("Authorize", Gtk.ResponseType.OK)
        self._dialog.set_position(Gtk.WindowPosition.CENTER)
        self._dialog.set_border_width(10)
        self._dialog.set_resizable(False)

        msg = "To use the Twitch indicator, you must authorize the app on the Twich website."
        label = Gtk.Label(label=msg)
        label.set_margin_bottom(16)
        self._dialog.get_content_area().add(label)
        self._dialog.show_all()

        try:
            if self._dialog.run() == Gtk.ResponseType.OK:
                self._gui_manager.app.start_auth(auth_event)
            else:
                GLib.idle_add(self._gui_manager.app.quit)
        finally:
            self._dialog.destroy()
            self._dialog = None

    def destroy(self) -> None:
        """Destroy dialog window."""
        if self._dialog is not None:
            self._dialog.destroy()
