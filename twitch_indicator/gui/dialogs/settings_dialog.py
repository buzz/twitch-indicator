import logging
from typing import TYPE_CHECKING, Optional, cast

from gi.repository import GLib, Gtk

from twitch_indicator.constants import REFRESH_INTERVAL_LIMITS
from twitch_indicator.gui.cached_profile_image import CachedProfileImage
from twitch_indicator.gui.dialogs.base import BaseDialog
from twitch_indicator.gui.dialogs.channel_chooser_dialog import ChannelChooserDialog

if TYPE_CHECKING:
    from twitch_indicator.gui.gui_manager import GuiManager


class SettingsDialog(BaseDialog[Gtk.Dialog]):
    """Twitch indicator settings dialog."""

    def __init__(self, gui_manager: "GuiManager") -> None:
        super().__init__("settings", gui_manager)
        self._logger = logging.getLogger(__name__)

        self._channel_chooser_dialog: Optional[ChannelChooserDialog] = None

        self._label_username = cast(Gtk.Label, self._builder.get_object("label_username"))
        self._image_profile = cast(Gtk.Image, self._builder.get_object("image_profile"))
        self._btn_loginout = cast(Gtk.Button, self._builder.get_object("btn_loginout"))
        self._switch_show_notifications = cast(
            Gtk.Switch, self._builder.get_object("switch_show_notifications")
        )
        self._switch_show_game = cast(Gtk.Switch, self._builder.get_object("switch_show_game"))
        self._switch_show_viewer_count = cast(
            Gtk.Switch, self._builder.get_object("switch_show_viewer_count")
        )
        self._switch_show_selected_channels_on_top = cast(
            Gtk.Switch, self._builder.get_object("switch_show_selected_channels_on_top")
        )
        self._entry_open_command = cast(Gtk.Entry, self._builder.get_object("open_command"))
        self._scale_refresh_interval = cast(
            Gtk.Scale, self._builder.get_object("scale_refresh_interval")
        )
        self._label_refresh_interval = cast(
            Gtk.Label, self._builder.get_object("label_refresh_interval")
        )
        self._btn_channel_chooser = cast(
            Gtk.Button, self._builder.get_object("btn_channel_chooser")
        )
        self._btn_revert_open_cmd = cast(
            Gtk.Button, self._builder.get_object("btn_revert_open_cmd")
        )

        self._setup_events()

    def run(self) -> None:
        """Run settings dialog."""
        self._apply_data()
        self._dialog.show_all()

        # Run dialog
        if self._dialog.run() == Gtk.ResponseType.OK:
            self._commit()

        self.destroy()

    def destroy(self) -> None:
        """Destroy dialog window."""
        if self._channel_chooser_dialog is not None:
            self._channel_chooser_dialog.destroy()
        super().destroy()

    def present(self) -> None:
        """Present window."""
        super().present()
        if self._channel_chooser_dialog:
            self._channel_chooser_dialog.present()

    def _setup_events(self) -> None:
        """Setup events."""
        super()._setup_events()
        self._gui_manager.app.state.add_handler("user", lambda _: self._update_user())
        self._gui_manager.app.state.add_handler(
            "followed_channels", lambda _: self._update_btn_channel_chooser()
        )

    def _apply_data(self) -> None:
        """Apply settings state to local controls."""
        settings = self._gui_manager.app.settings
        self._switch_show_notifications.set_active(settings.get_boolean("enable-notifications"))
        self._switch_show_game.set_active(settings.get_boolean("show-game-playing"))
        self._switch_show_viewer_count.set_active(settings.get_boolean("show-viewer-count"))
        self._switch_show_selected_channels_on_top.set_active(
            settings.get_boolean("show-selected-channels-on-top")
        )
        self._entry_open_command.set_text(settings.get_string("open-command"))

        # refresh interval scale
        self._adjustment = self._scale_refresh_interval.get_adjustment()
        self._adjustment.set_lower(REFRESH_INTERVAL_LIMITS[0])
        self._adjustment.set_upper(REFRESH_INTERVAL_LIMITS[1])
        for mark in (1, 5, 10, 15):
            self._scale_refresh_interval.add_mark(mark, Gtk.PositionType.BOTTOM, str(mark))
        self._scale_refresh_interval.set_value(settings.get_double("refresh-interval"))
        val = settings.get_double("refresh-interval")
        self._scale_refresh_interval.set_value(val)
        self._update_label_refresh_interval(val)

        self._update_user()
        self._update_btn_channel_chooser()

    def _commit(self) -> None:
        """Commit changes to app state."""
        settings = self._gui_manager.app.settings
        settings.set_boolean("enable-notifications", self._switch_show_notifications.get_active())
        settings.set_boolean("show-game-playing", self._switch_show_game.get_active())
        settings.set_boolean("show-viewer-count", self._switch_show_viewer_count.get_active())
        settings.set_boolean(
            "show-selected-channels-on-top",
            self._switch_show_selected_channels_on_top.get_active(),
        )
        settings.set_string("open-command", self._entry_open_command.get_text())
        settings.set_double("refresh-interval", self._scale_refresh_interval.get_value())

    def _update_user(self) -> None:
        """Update user info area."""
        self._logger.debug("_update_user()")
        with self._gui_manager.app.state.locks["user"]:
            user = self._gui_manager.app.state.user
        self._logger.debug(f"_update_user(): {user}")
        if user is None:
            self._image_profile.set_from_pixbuf(CachedProfileImage.new_app_image(variant="icon"))
            self._btn_loginout.set_label("Log In")
            self._label_username.set_markup("<i>Logged Out</i>")
        else:
            self._image_profile.set_from_pixbuf(
                CachedProfileImage.new_from_cached(user.id, variant="icon")
            )
            self._btn_loginout.set_label("Log Out")
            self._label_username.set_markup(f"<b>{user.display_name}</b>")

    def _show_channel_chooser(self) -> None:
        """Show channel chooser dialog."""
        self._channel_chooser_dialog = ChannelChooserDialog(self._gui_manager)
        self._channel_chooser_dialog.run()
        self._channel_chooser_dialog = None

    def _update_btn_channel_chooser(self, enabled=True) -> None:
        """Enable channel chooser button."""
        with self._gui_manager.app.state.locks["followed_channels"]:
            has_followers = bool(self._gui_manager.app.state.followed_channels)
        self._btn_channel_chooser.set_sensitive(has_followers)

    def _update_label_refresh_interval(self, value: float) -> None:
        """Update refresh interval label."""
        if self._label_refresh_interval:
            str_value = "30 seconds" if value == 0.5 else f"{value} minutes"
            self._label_refresh_interval.set_text(str_value)

    def _on_btn_loginout_clicked(self, btn: Gtk.Button) -> None:
        """Log out user."""
        with self._gui_manager.app.state.locks["user"]:
            user = self._gui_manager.app.state.user
        if user is None:
            GLib.idle_add(self._gui_manager.app.login)
        else:
            self._gui_manager.app.logout()

    def _on_btn_channel_chooser_clicked(self, btn: Gtk.Button) -> None:
        """Callback for channel chooser menu item."""
        try:
            self._dialog.set_sensitive(False)
            self._show_channel_chooser()
        finally:
            self._dialog.set_sensitive(True)

    def _on_btn_revert_open_cmd_clicked(self, btn: Gtk.Button) -> None:
        """Revert open command to default."""
        settings = self._gui_manager.app.settings
        val = settings.get_default_value("open-command")
        if val is not None:
            self._entry_open_command.set_text(val.get_string())

    def _on_refresh_interval_value_changed(self, scale: Gtk.Scale) -> None:
        """Enforce increments of 0.5."""
        value = round(scale.get_value() * 2) / 2
        scale.set_value(value)
        self._update_label_refresh_interval(value)
