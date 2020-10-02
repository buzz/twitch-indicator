from gi.repository import Gio, Gtk

from twitch_indicator.constants import SETTINGS_KEY
from twitch_indicator.util import get_data_filepath


class Settings:
    """Twitch indicator settings dialog."""

    def __init__(self):
        self.settings = Gio.Settings.new(SETTINGS_KEY)

    def get(self):
        """Return settings object."""
        return self.settings

    def show(self):
        """Shows applet settings dialog."""
        dialog = Gtk.Dialog("Settings", None, 0)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )
        dialog.set_position(Gtk.WindowPosition.CENTER)

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
        builder.get_object("refresh_interval").set_value(
            self.settings.get_int("refresh-interval")
        )

        box = dialog.get_content_area()
        box.add(builder.get_object("grid1"))
        response = dialog.run()

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
            self.settings.set_int(
                "refresh-interval",
                builder.get_object("refresh_interval").get_value_as_int(),
            )

        dialog.destroy()
