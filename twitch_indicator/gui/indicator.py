from gi.repository import AppIndicator3, GdkPixbuf, GLib, Gtk

from twitch_indicator.gui.cached_profile_image import CachedProfileImage
from twitch_indicator.utils import (
    build_stream_url,
    format_viewer_count,
    get_data_filepath,
    open_stream,
)


class Indicator:
    """App indicator."""

    def __init__(self, gui_manager):
        self._gui_manager = gui_manager
        self._app_indicator = AppIndicator3.Indicator.new(
            "Twitch indicator",
            get_data_filepath("twitch-indicator.svg"),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._app_indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self._setup_menu()
        self._gui_manager.app.state.add_handler(
            "live_streams", self._update_streams_menu
        )

    def _setup_menu(self):
        """Setup menu."""
        self.menu = Gtk.Menu()

        self.menu_item_channels = Gtk.MenuItem(label="Live channels")
        self.menu_item_channels.set_sensitive(False)

        self.menu_item_settings = Gtk.MenuItem(label="Settings")
        self.menu_item_settings.connect("activate", self._on_settings)

        self.menu_item_quit = Gtk.MenuItem(label="Quit")
        self.menu_item_quit.connect("activate", self._on_quit)

        self._app_indicator.set_menu(self.menu)
        self._refresh_menu_items()

    def _update_streams_menu(self, live_streams):
        """Update stream list."""
        settings = self._gui_manager.app.settings

        streams_menu = Gtk.Menu()
        self.menu_item_channels.set_submenu(streams_menu)

        # Order streams by viewer count
        with self._gui_manager.app.state.locks["live_streams"]:
            streams_ordered = sorted(live_streams, key=lambda k: -k["viewer_count"])

        if streams_ordered:
            self.menu_item_channels.set_label(f"Live channels ({len(streams_ordered)})")
            self.menu_item_channels.set_sensitive(True)

            # Selected channels to top
            if settings.get_boolean("show-selected-channels-on-top"):
                enabled_channels = []
                other_channels = []

                with self._gui_manager.app.state.locks["enabled_channel_ids"]:
                    state = self._gui_manager.app.state
                    enabled_channel_ids = state.enabled_channel_ids
                    for stream in streams_ordered:
                        try:
                            if enabled_channel_ids[stream["user_id"]]:
                                enabled_channels.append(stream)
                            else:
                                other_channels.append(stream)
                        except KeyError:
                            other_channels.append(stream)

                self._create_channel_menu_items(
                    enabled_channels, streams_menu, settings
                )
                streams_menu.append(Gtk.SeparatorMenuItem())
                self._create_channel_menu_items(other_channels, streams_menu, settings)

            else:
                self._create_channel_menu_items(streams_ordered, streams_menu, settings)

        else:
            # No live channels
            self.menu_item_channels.set_label("No live channels...")
            self.menu_item_channels.set_sensitive(False)

        self._refresh_menu_items()

    def _create_channel_menu_items(self, streams, streams_menu, settings):
        """Create menu items from streams array."""
        for stream in streams:
            menu_entry = Gtk.ImageMenuItem()

            # Channel icon
            pixbuf = CachedProfileImage.new_from_cached(stream["user_id"])
            pixbuf.scale_simple(32, 32, GdkPixbuf.InterpType.BILINEAR)
            icon = Gtk.Image.new_from_pixbuf(pixbuf)
            menu_entry.set_image(icon)

            # Channel label
            label = Gtk.Label()
            markup = f"<b>{GLib.markup_escape_text(stream['user_name'])}</b>"
            if settings.get_boolean("show-game-playing") and stream["game_name"]:
                markup += f" • {GLib.markup_escape_text(stream['game_name'])}"
            if settings.get_boolean("show-viewer-count"):
                viewer_count = format_viewer_count(stream["viewer_count"])
                markup += f" (<small>{viewer_count}</small>)"

            label.set_markup(markup)
            label.set_halign(Gtk.Align.START)
            menu_entry.add(label)
            url = build_stream_url(stream["user_login"])
            menu_entry.connect("activate", self._on_stream_menu, url)

            streams_menu.append(menu_entry)

    def _refresh_menu_items(self):
        """Refresh all menu by removing and re-adding menu items."""
        for menu_item in self.menu.get_children():
            self.menu.remove(menu_item)
        self.menu.append(self.menu_item_channels)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(self.menu_item_settings)
        self.menu.append(self.menu_item_quit)
        self.menu.show_all()

    # UI callbacks

    def _on_quit(self, _):
        """Callback for quit menu item."""
        self._gui_manager.app.quit()

    def _on_settings(self, _):
        """Callback for settings menu item."""
        self._gui_manager.show_settings()

    def _on_stream_menu(self, _, url):
        """Callback for stream menu item."""
        open_cmd = self._gui_manager.app.settings.get_string("open-command")
        open_stream(url, open_cmd)
