import abc
from typing import TYPE_CHECKING, Generic, TypeVar, cast

from gi.repository import Gtk

from twitch_indicator.utils import get_data_file

if TYPE_CHECKING:
    from twitch_indicator.gui.gui_manager import GuiManager

_T = TypeVar("_T", bound=Gtk.Dialog)


class BaseDialog(abc.ABC, Generic[_T]):
    def __init__(self, name: str, gui_manager: "GuiManager") -> None:
        self._gui_manager = gui_manager
        self._builder = Gtk.Builder()
        self._builder.add_from_file(str(get_data_file(f"{name}.glade")))
        self._dialog = cast(_T, self._builder.get_object("dialog"))

    def run(self) -> None:
        """Run dialog."""
        self._dialog.show_all()
        try:
            self._dialog.run()
        finally:
            self._dialog.destroy()

    def destroy(self) -> None:
        """Destroy dialog window."""
        if self._dialog is not None:
            self._dialog.destroy()

    def present(self) -> None:
        self._dialog.present()

    def _setup_events(self) -> None:
        """Setup events."""
        self._builder.connect_signals(self)
