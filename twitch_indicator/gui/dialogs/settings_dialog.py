from typing import TYPE_CHECKING, Optional, cast

from gi.repository import Gtk

from twitch_indicator.constants import REFRESH_INTERVAL_LIMITS
from twitch_indicator.utils import get_data_file

if TYPE_CHECKING:
    from twitch_indicator.gui.gui_manager import GuiManager


class SettingsDialog:
    """Twitch indicator settings dialog."""

    def __init__(self, gui_manager: "GuiManager") -> None:
        self._gui_manager = gui_manager
        self._reset_attributes()

    def _reset_attributes(self) -> None:
        self._dialog: Optional[Gtk.Dialog] = None
        self._entry_open_command: Optional[Gtk.Entry] = None
        self._btn_channel_chooser: Optional[Gtk.Button] = None
        self._label_refresh_interval: Optional[Gtk.Label] = None

    def show(self) -> None:
        """Shows applet settings dialog."""
        if self._dialog:
            self._dialog.present()
            self._gui_manager.channel_chooser_dialog.present()
            return

        settings = self._gui_manager.app.settings

        # dialog
        self._dialog = Gtk.Dialog(title="Settings")
        self._dialog.set_border_width(10)
        self._dialog.set_resizable(False)
        self._dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self._dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self._dialog.set_position(Gtk.WindowPosition.CENTER)

        # builder
        builder = Gtk.Builder()
        builder.add_from_file(str(get_data_file("twitch-indicator-settings.glade")))

        # get widgets
        grid = cast(Gtk.Grid, builder.get_object("grid"))
        switch_show_notifications = cast(
            Gtk.Switch, builder.get_object("switch_show_notifications")
        )
        switch_show_game = cast(Gtk.Switch, builder.get_object("switch_show_game"))
        switch_show_viewer_count = cast(Gtk.Switch, builder.get_object("switch_show_viewer_count"))
        switch_show_selected_channels_on_top = cast(
            Gtk.Switch, builder.get_object("switch_show_selected_channels_on_top")
        )
        self._entry_open_command = cast(Gtk.Entry, builder.get_object("open_command"))
        scale_refresh_interval = cast(Gtk.Scale, builder.get_object("scale_refresh_interval"))
        self._label_refresh_interval = cast(Gtk.Label, builder.get_object("label_refresh_interval"))
        self._btn_channel_chooser = cast(Gtk.Button, builder.get_object("btn_channel_chooser"))
        btn_revert_open_cmd = cast(Gtk.Button, builder.get_object("btn_revert_open_command"))

        # apply settings values to controls
        switch_show_notifications.set_active(settings.get_boolean("enable-notifications"))
        switch_show_game.set_active(settings.get_boolean("show-game-playing"))
        switch_show_viewer_count.set_active(settings.get_boolean("show-viewer-count"))
        switch_show_selected_channels_on_top.set_active(
            settings.get_boolean("show-selected-channels-on-top")
        )
        self._entry_open_command.set_text(settings.get_string("open-command"))

        # refresh interval scale
        adjustment = scale_refresh_interval.get_adjustment()
        adjustment.set_lower(REFRESH_INTERVAL_LIMITS[0])
        adjustment.set_upper(REFRESH_INTERVAL_LIMITS[1])
        for mark in (1, 5, 10, 15):
            scale_refresh_interval.add_mark(mark, Gtk.PositionType.BOTTOM, str(mark))
        scale_refresh_interval.set_value(settings.get_double("refresh-interval"))
        val = settings.get_double("refresh-interval")
        scale_refresh_interval.set_value(val)
        self._update_label_refresh_interval(val)

        # add layout to dialog
        box = self._dialog.get_content_area()
        box.add(grid)

        # events
        btn_revert_open_cmd.connect("clicked", self._on_btn_revert_open_commed_clicked)
        scale_refresh_interval.connect("value-changed", self._on_refresh_interval_value_changed)
        self._btn_channel_chooser.connect("clicked", self._on_btn_channel_chooser_clicked)

        self._enable_btn_channel_chooser()
        self._dialog.show_all()

        if self._dialog.run() == Gtk.ResponseType.OK:
            settings.set_boolean("enable-notifications", switch_show_notifications.get_active())
            settings.set_boolean("show-game-playing", switch_show_game.get_active())
            settings.set_boolean("show-viewer-count", switch_show_viewer_count.get_active())
            settings.set_boolean(
                "show-selected-channels-on-top",
                switch_show_selected_channels_on_top.get_active(),
            )
            settings.set_string("open-command", self._entry_open_command.get_text())
            settings.set_double("refresh-interval", scale_refresh_interval.get_value())

        self.destroy()

    def destroy(self) -> None:
        """Destroy dialog window."""
        if self._dialog is not None:
            self._dialog.destroy()
        self._reset_attributes()

    def _enable_btn_channel_chooser(self, enabled=True) -> None:
        """Enable channel chooser button."""
        if self._btn_channel_chooser is not None:
            with self._gui_manager.app.state.locks["followed_channels"]:
                has_followers = bool(self._gui_manager.app.state.followed_channels)
            label = "Choose channels" if has_followers else "Choose channels (Loading…)"
            self._btn_channel_chooser.set_label(label)
            self._btn_channel_chooser.set_sensitive(has_followers)

    def _update_label_refresh_interval(self, value: float) -> None:
        """Update refresh interval label."""
        if self._label_refresh_interval:
            str_value = "30 seconds" if value == 0.5 else f"{value} minutes"
            self._label_refresh_interval.set_text(str_value)

    def _on_btn_channel_chooser_clicked(self, btn: Gtk.Button) -> None:
        """Callback for channel chooser menu item."""
        if self._dialog is not None:
            try:
                self._dialog.set_sensitive(False)
                self._gui_manager.show_channel_chooser(self._dialog)
            finally:
                if self._dialog is not None:
                    self._dialog.set_sensitive(True)

    def _on_btn_revert_open_commed_clicked(self, btn: Gtk.Button) -> None:
        """Revert open command to default."""
        if self._entry_open_command is not None:
            settings = self._gui_manager.app.settings
            val = settings.get_default_value("open-command")
            if val is not None:
                self._entry_open_command.set_text(val.get_string())

    def _on_refresh_interval_value_changed(self, scale: Gtk.Scale) -> None:
        """Enforce increments of 0.5."""
        value = round(scale.get_value() * 2) / 2
        scale.set_value(value)
        self._update_label_refresh_interval(value)
