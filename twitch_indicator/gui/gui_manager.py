from gi.repository import Gdk, Gtk

from twitch_indicator.gui.dialogs.auth_dialog import AuthDialog
from twitch_indicator.gui.dialogs.channel_chooser_dialog import ChannelChooserDialog
from twitch_indicator.gui.dialogs.settings_dialog import SettingsDialog
from twitch_indicator.gui.indicator import Indicator
from twitch_indicator.gui.notifications import Notifications
from twitch_indicator.utils import get_data_filepath


class GuiManager:
    def __init__(self, app):
        self.app = app
        self.settings_dialog = SettingsDialog(self)
        self.channel_chooser_dialog = ChannelChooserDialog(self)
        self.indicator = Indicator(self)
        self.notifications = Notifications(self)
        self.auth_dialog = AuthDialog(self)

        self._setup_css_provider()

    def run(self):
        """Run Gtk main loop."""
        Gtk.main()

    def quit(self):
        """Destroy windows and quit."""
        self.auth_dialog.destroy()
        self.settings_dialog.destroy()
        self.channel_chooser_dialog.destroy()

        Gtk.main_quit()

    def show_channel_chooser(self, settings_dialog):
        """Show channel chooser dialog."""
        self.channel_chooser_dialog.show(settings_dialog)

    def show_settings(self):
        """Show settings dialog."""
        self.settings_dialog.show()

    def show_auth_dialog(self, auth_event):
        """Show authentication dialog."""
        self.auth_dialog.show(auth_event)

    def _setup_css_provider(self):
        """Setup CSS provider."""
        screen = Gdk.Screen.get_default()
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(get_data_filepath("style.css"))
        Gtk.StyleContext.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
