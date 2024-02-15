from typing import TYPE_CHECKING, Iterable

from gi.repository import AppIndicator3, GLib, Gtk

from twitch_indicator.api.models import Stream
from twitch_indicator.gui.cached_profile_image import CachedProfileImage
from twitch_indicator.settings import Settings
from twitch_indicator.state import ChannelState
from twitch_indicator.utils import format_viewer_count, get_data_file

if TYPE_CHECKING:
    from twitch_indicator.gui.gui_manager import GuiManager


class Indicator:
    """App indicator."""

    def __init__(self, gui_manager: "GuiManager") -> None:
        self._gui_manager = gui_manager
        self._app_indicator = AppIndicator3.Indicator.new(
            "Twitch indicator",
            str(get_data_file("twitch-indicator.svg")),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._app_indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        self._menu_streams = Gtk.Menu()
        self._menu_item_streams = Gtk.MenuItem.new()
        self._setup_menu()
        self._setup_events()

    def _setup_events(self) -> None:
        self._gui_manager.app.state.add_handler(
            "validation_info", lambda _: self._update_menu_item_streams()
        )
        self._gui_manager.app.state.add_handler(
            "live_streams", lambda _: self._update_streams_menu()
        )
        self._gui_manager.app.settings.settings.connect(
            "changed::show-selected-channels-on-top",
            lambda *_: self._update_streams_menu(),
        )

    def _setup_menu(self) -> None:
        """Setup menu."""

        # Root menu
        menu = Gtk.Menu()
        menu.insert_action_group("menu", self._gui_manager.app.actions.action_group)

        # Streams menu
        self._menu_item_streams.set_sensitive(False)
        self._menu_item_streams.set_submenu(self._menu_streams)
        menu.append(self._menu_item_streams)

        menu.append(Gtk.SeparatorMenuItem.new())

        # Actions menu (settings, quit)
        menu_item_settings = Gtk.MenuItem.new_with_label("Settings")
        menu_item_quit = Gtk.MenuItem.new_with_label("Quit")

        menu_item_settings.set_action_name("menu.settings")
        menu_item_quit.set_action_name("menu.quit")

        menu.append(menu_item_settings)
        menu.append(menu_item_quit)

        self._update_menu_item_streams()
        menu.show_all()
        self._app_indicator.set_menu(menu)

    def _update_menu_item_streams(self) -> None:
        """Update live streams menu item label."""
        with self._gui_manager.app.state.locks["validation_info"]:
            logged_out = self._gui_manager.app.state.validation_info is None

        label = "Logged out..."
        sensitive = False

        if not logged_out:
            with self._gui_manager.app.state.locks["live_streams"]:
                stream_count = len(self._gui_manager.app.state.live_streams)
            if stream_count > 0:
                label = f"Live streams ({stream_count})"
                sensitive = True
            else:
                label = "No live streams..."

        self._menu_item_streams.set_label(label)
        self._menu_item_streams.set_sensitive(sensitive)

    def _update_streams_menu(self) -> None:
        """Update stream list."""
        settings = self._gui_manager.app.settings
        menu = self._menu_streams

        # Order streams by viewer count
        with self._gui_manager.app.state.locks["live_streams"]:
            streams = sorted(
                self._gui_manager.app.state.live_streams, key=lambda s: -s.viewer_count
            )

        # Live streams?
        if streams:
            # Clear menu
            for item in menu.get_children():
                menu.remove(item)

            # Selected streams to top
            if settings.get_boolean("show-selected-channels-on-top"):
                with self._gui_manager.app.state.locks["enabled_channel_ids"]:
                    ec_ids = self._gui_manager.app.state.enabled_channel_ids.items()
                    top_ids = [uid for uid, en in ec_ids if en == ChannelState.ENABLED]

                top_streams = (s for s in streams if s.user_id in top_ids)
                self._create_stream_menu_item(menu, top_streams, settings)

                menu.append(Gtk.SeparatorMenuItem.new())

                bottom_streams = (s for s in streams if s.user_id not in top_ids)
                self._create_stream_menu_item(menu, bottom_streams, settings)
            else:
                self._create_stream_menu_item(menu, streams, settings)

        self._update_menu_item_streams()
        menu.show_all()

    @staticmethod
    def _create_stream_menu_item(
        menu: Gtk.Menu, streams: Iterable[Stream], settings: Settings
    ) -> None:
        """Create menu item for stream."""

        for stream in streams:
            menu_item = Gtk.ImageMenuItem()
            menu_item.set_detailed_action_name(f"menu.open-stream::{stream.user_login}")

            # User profile image icon
            pixbuf = CachedProfileImage.new_from_cached(stream.user_id, "icon")
            menu_item.set_image(Gtk.Image.new_from_pixbuf(pixbuf))

            # Label
            label = Gtk.Label()
            markup = f"<b>{GLib.markup_escape_text(stream.user_name)}</b>"
            if settings.get_boolean("show-game-playing") and stream.game_name:
                markup += f" • {GLib.markup_escape_text(stream.game_name)}"
            if settings.get_boolean("show-viewer-count"):
                viewer_count = format_viewer_count(stream.viewer_count)
                markup += f" (<small>{viewer_count}</small>)"
            label.set_markup(markup)
            label.set_halign(Gtk.Align.START)
            menu_item.add(label)

            menu.append(menu_item)
