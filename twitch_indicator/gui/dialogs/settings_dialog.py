from gi.repository import Gtk

from twitch_indicator.constants import REFRESH_INTERVAL_LIMITS
from twitch_indicator.util import get_data_filepath


class SettingsDialog:
    """Twitch indicator settings dialog."""

    def __init__(self, gui_manager):
        self._gui_manager = gui_manager
        self._reset_attributes()

    def _reset_attributes(self):
        self._dialog = None
        self._entry_open_command = None
        self._btn_channel_chooser = None
        self._label_refresh_interval = None

    def show(self):
        """Shows applet settings dialog."""
        if self._dialog:
            self._dialog.present()
            self._gui_manager.channel_chooser_dialog.show(skip_create=True)
            return

        settings = self._gui_manager.app.settings

        self._dialog = Gtk.Dialog("Settings", None, 0)
        self._dialog.set_border_width(10)
        self._dialog.set_resizable(False)
        self._dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )
        self._dialog.set_position(Gtk.WindowPosition.CENTER)

        builder = Gtk.Builder()
        builder.add_from_file(get_data_filepath("twitch-indicator-settings.glade"))

        toggle_show_notifications = builder.get_object("show_notifications")
        toggle_show_game = builder.get_object("show_game")
        toggle_show_viewer_count = builder.get_object("show_viewer_count")
        toggle_show_selected_channels_on_top = builder.get_object(
            "show_selected_channels_on_top"
        )
        self._entry_open_command = builder.get_object("open_command")
        scale_refresh_interval = builder.get_object("refresh_interval")
        self._label_refresh_interval = builder.get_object("label_refresh_interval")
        self._btn_channel_chooser = builder.get_object("btn_channel_chooser")

        toggle_show_notifications.set_active(
            settings.get_boolean("enable-notifications")
        )
        toggle_show_game.set_active(settings.get_boolean("show-game-playing"))
        toggle_show_viewer_count.set_active(settings.get_boolean("show-viewer-count"))
        toggle_show_selected_channels_on_top.set_active(
            settings.get_boolean("show-selected-channels-on-top")
        )
        self._entry_open_command.set_text(settings.get_string("open-command"))

        builder.get_object("btn_revert_open_command").connect(
            "clicked", self._on_btn_revert_open_commed_clicked
        )

        adjustment = scale_refresh_interval.get_adjustment()
        adjustment.set_lower(REFRESH_INTERVAL_LIMITS[0])
        adjustment.set_upper(REFRESH_INTERVAL_LIMITS[1])
        for mark in (1, 5, 10, 15):
            scale_refresh_interval.add_mark(mark, Gtk.PositionType.BOTTOM, str(mark))
        scale_refresh_interval.set_value(settings.get_double("refresh-interval"))
        scale_refresh_interval.connect(
            "value-changed", self._on_refresh_interval_value_changed
        )
        val = settings.get_double("refresh-interval")
        scale_refresh_interval.set_value(val)
        self._update_label_refresh_interval(val)

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
            val = toggle_show_notifications.get_active()
            settings.set_boolean("enable-notifications", val)
            val = toggle_show_game.get_active()
            settings.set_boolean("show-game-playing", val)
            val = toggle_show_viewer_count.get_active()
            settings.set_boolean("show-viewer-count", val)
            val = toggle_show_selected_channels_on_top.get_active()
            settings.set_boolean("show-selected-channels-on-top", val)
            val = self._entry_open_command.get_text()
            settings.set_string("open-command", val)
            val = scale_refresh_interval.get_value()
            settings.set_double("refresh-interval", val)

        self.destroy()

    def destroy(self):
        """Destroy dialog window."""
        try:
            self._dialog.destroy()
        except AttributeError:
            pass
        self._reset_attributes()

    def _update_label_refresh_interval(self, value):
        """Update refresh interval label."""
        if self._label_refresh_interval:
            str_value = "30 seconds" if value == 0.5 else f"{value} minutes"
            self._label_refresh_interval.set_text(str_value)

    def _on_btn_channel_chooser_clicked(self, _):
        """Callback for channel chooser menu item."""
        self._dialog.set_sensitive(False)
        try:
            self._gui_manager.show_channel_chooser(self._dialog)
        finally:
            try:
                self._dialog.set_sensitive(True)
            except AttributeError:
                pass

    def _on_btn_revert_open_commed_clicked(self, _):
        """Revert open command to default."""
        settings = self._gui_manager.app.settings
        val = settings.get_default_value("open-command")
        self._entry_open_command.set_text(val.get_string())

    def _on_refresh_interval_value_changed(self, range):
        """Enforce increments of 0.5."""
        value = round(range.get_value() * 2) / 2
        range.set_value(value)
        self._update_label_refresh_interval(value)
