from gi.repository import GLib, Gtk

from twitch_indicator.util import get_data_filepath


class AuthDialog:
    def __init__(self, gui_manager):
        self._gui_manager = gui_manager
        self._dialog = None

    def show(self, auth_event):
        self._dialog = Gtk.Dialog("Twitch authentication", None, 0)
        self._dialog.add_buttons(
            Gtk.STOCK_QUIT, Gtk.ResponseType.CANCEL, "Authorize", Gtk.ResponseType.OK
        )
        self._dialog.set_position(Gtk.WindowPosition.CENTER)

        builder = Gtk.Builder()
        builder.add_from_file(get_data_filepath("twitch-indicator-auth.glade"))

        box = self._dialog.get_content_area()
        box.add(builder.get_object("grid"))

        response = self._dialog.run()
        try:
            if response == Gtk.ResponseType.OK:
                self._gui_manager.app.start_auth(auth_event)
            else:
                GLib.idle_add(self._gui_manager.app.quit)
        finally:
            self._dialog.destroy()
            self._dialog = None

    def destroy(self):
        """Destroy dialog window."""
        try:
            self._dialog.destroy()
        except AttributeError:
            pass
