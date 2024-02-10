from gi.repository import Gtk

from twitch_indicator.util import get_data_filepath


class SettingsDialog:
    """Twitch indicator settings dialog."""

    def __init__(self, gui_manager):
        self._gui_manager = gui_manager
        self._dialog = None
        self._entry_open_command = None
        self._btn_channel_chooser = None

    def show(self):
        """Shows applet settings dialog."""
        if self._dialog:
            self._dialog.present()
            self._gui_manager.channel_chooser_dialog.show(skip_create=True)
            return

        settings = self._gui_manager.app.settings

        self._dialog = Gtk.Dialog("Settings", None, 0)
        self._dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )
        self._dialog.set_position(Gtk.WindowPosition.CENTER)

        builder = Gtk.Builder()
        builder.add_from_file(get_data_filepath("twitch-indicator-settings.glade"))

        val = settings.get_boolean("enable-notifications")
        builder.get_object("show_notifications").set_active(val)
        val = settings.get_boolean("show-game-playing")
        builder.get_object("show_game").set_active(val)
        val = settings.get_boolean("show-viewer-count")
        builder.get_object("show_viewer_count").set_active(val)
        val = settings.get_boolean("show-selected-channels-on-top")
        builder.get_object("show_selected_channels_on_top").set_active(val)
        self._entry_open_command = builder.get_object("open_command")
        self._entry_open_command.set_text(settings.get_string("open-command"))

        cb = self._on_btn_revert_open_commed_clicked
        builder.get_object("btn_revert_open_command").connect("clicked", cb)

        spin_btn_refresh_interval = builder.get_object("refresh_interval")
        spin_btn_refresh_interval.set_range(1, 999)
        spin_btn_refresh_interval.set_increments(1, 1)
        spin_btn_refresh_interval.set_value(settings.get_int("refresh-interval"))

        self._btn_channel_chooser = builder.get_object("btn_channel_chooser")
        self._btn_channel_chooser.connect(
            "clicked", self._on_btn_channel_chooser_clicked
        )

        with self._gui_manager.app.state.locks["followed_channels"]:
            has_followers = bool(self._gui_manager.app.state.followed_channels)
        if has_followers:
            self._btn_channel_chooser.set_label("Choose channels")
            self._btn_channel_chooser.set_sensitive(True)

        box = self._dialog.get_content_area()
        box.add(builder.get_object("grid1"))
        response = self._dialog.run()

        if response == Gtk.ResponseType.OK:
            val = builder.get_object("show_notifications").get_active()
            settings.set_boolean("enable-notifications", val)
            val = builder.get_object("show_game").get_active()
            settings.set_boolean("show-game-playing", val)
            val = builder.get_object("show_viewer_count").get_active()
            settings.set_boolean("show-viewer-count", val)
            val = builder.get_object("show_selected_channels_on_top").get_active()
            settings.set_boolean("show-selected-channels-on-top", val)
            val = builder.get_object("open_command").get_text()
            settings.set_string("open-command", val)
            val = builder.get_object("refresh_interval").get_value_as_int()
            settings.set_int("refresh-interval", val)

        self.destroy()

    def destroy(self):
        """Destroy dialog window."""
        try:
            self._dialog.destroy()
        except AttributeError:
            pass
        self._dialog = None
        self._entry_open_command = None
        self._btn_channel_chooser = None

    def enable_channel_chooser(self):
        """Enable channel chooser button."""
        try:
            self._btn_channel_chooser.set_label("Choose channels")
            self._btn_channel_chooser.set_sensitive(True)
        except AttributeError:
            pass

    def _on_btn_channel_chooser_clicked(self, _):
        """Callback for channel chooser menu item."""
        self._dialog.set_sensitive(False)
        try:
            self._gui_manager.show_channel_chooser()
        finally:
            self._dialog.set_sensitive(True)

    def _on_btn_revert_open_commed_clicked(self, _):
        """Revert open command to default."""
        settings = self._gui_manager.app.settings
        val = settings.get_default_value("open-command")
        self._entry_open_command.set_text(val.get_string())
