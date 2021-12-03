from gi.repository import Gio, Gtk

from twitch_indicator.constants import SETTINGS_KEY
from twitch_indicator.util import get_data_filepath


class Settings:
    """Twitch indicator settings dialog."""

    def __init__(self, app):
        self.app = app
        self.settings = Gio.Settings.new(SETTINGS_KEY)
        self.dialog = None
        self.btn_channel_chooser = None

    def get(self):
        """Return settings object."""
        return self.settings

    def show(self):
        """Shows applet settings dialog."""
        if self.dialog:
            self.dialog.present()
            if self.app.channel_chooser.dialog:
                self.app.channel_chooser.show()
            return

        self.dialog = Gtk.Dialog("Settings", None, 0)
        self.dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )
        self.dialog.set_position(Gtk.WindowPosition.CENTER)

        builder = Gtk.Builder()
        builder.add_from_file(get_data_filepath("twitch-indicator-settings.glade"))

        builder.get_object("show_notifications").set_active(
            self.settings.get_boolean("enable-notifications")
        )
        builder.get_object("show_game").set_active(
            self.settings.get_boolean("show-game-playing")
        )
        builder.get_object("show_viewer_count").set_active(
            self.settings.get_boolean("show-viewer-count")
        )
        builder.get_object("open_command").set_text(
            self.settings.get_string("open-command")
        )
        builder.get_object("refresh_interval").set_value(
            self.settings.get_int("refresh-interval")
        )
        self.btn_channel_chooser = builder.get_object("btn_channel_chooser")
        self.btn_channel_chooser.connect("clicked", self.on_btn_channel_chooser_clicked)
        if self.app.followed_channels:
            self.btn_channel_chooser.set_label("Choose channels")
            self.btn_channel_chooser.set_sensitive(True)

        box = self.dialog.get_content_area()
        box.add(builder.get_object("grid1"))
        response = self.dialog.run()

        if response == Gtk.ResponseType.OK:
            self.settings.set_boolean(
                "enable-notifications",
                builder.get_object("show_notifications").get_active(),
            )
            self.settings.set_boolean(
                "show-game-playing", builder.get_object("show_game").get_active()
            )
            self.settings.set_boolean(
                "show-viewer-count",
                builder.get_object("show_viewer_count").get_active(),
            )
            self.settings.set_string(
                "open-command",
                builder.get_object("open_command").get_text(),
            )
            self.settings.set_int(
                "refresh-interval",
                builder.get_object("refresh_interval").get_value_as_int(),
            )

        try:
            self.dialog.destroy()
        except AttributeError:
            pass
        self.dialog = None

    def enable_channel_chooser(self):
        """Enable channel chooser button."""
        try:
            self.btn_channel_chooser.set_label("Choose channels")
            self.btn_channel_chooser.set_sensitive(True)
        except AttributeError:
            pass

    def on_btn_channel_chooser_clicked(self, _):
        """Callback for channel chooser menu item."""
        self.app.show_channel_chooser()
