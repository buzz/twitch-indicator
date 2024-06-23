from typing import TYPE_CHECKING, Iterable

from gi.repository import GLib, Gtk, XApp

from twitch_indicator.api.models import Stream
from twitch_indicator.gui.cached_profile_image import CachedProfileImage
from twitch_indicator.settings import Settings
from twitch_indicator.state import ChannelState
from twitch_indicator.utils import format_viewer_count

if TYPE_CHECKING:
    from twitch_indicator.gui.gui_manager import GuiManager


class Indicator(XApp.StatusIcon):
    """App indicator."""

    LOGGED_OUT_TEXT = "Logged out..."

    def __init__(self, gui_manager: "GuiManager") -> None:
        super().__init__()
        self._gui_manager = gui_manager

        self.set_icon_name("twitch-indicator")
        self.set_label("Twitch Indicator")

        self._menu_streams = Gtk.Menu()
        self._menu_item_streams = Gtk.MenuItem.new()

        self._setup_menu()
        self._setup_events()

    def _setup_events(self) -> None:
        self._gui_manager.app.state.add_handler("user", lambda _: self._update_tooltip())
        self._gui_manager.app.state.add_handler(
            "validation_info", lambda _: self._update_menu_item_streams()
        )
        self._gui_manager.app.state.add_handler(
            "live_streams", lambda _: self._update_menu_item_streams()
        )
        self._gui_manager.app.state.add_handler(
            "live_streams", lambda _: self._update_streams_menu()
        )
        self._gui_manager.app.state.add_handler(
            "enabled_channel_ids", lambda _: self._update_streams_menu()
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

        menu_item_settings.set_action_name("menu.settings")
        menu_item_quit.set_action_name("menu.quit")

        menu.append(menu_item_settings)
        menu.append(menu_item_quit)

        self._menu_item_streams.set_label("No live streams...")
        self._menu_item_streams.set_sensitive(False)

        menu.show_all()
        self.set_primary_menu(menu)
        self.set_secondary_menu(menu)

    def _update_tooltip(self):
        """Update indicator tooltip text."""
        state = self._gui_manager.app.state
        with state.locks["user"]:
            if state.user is None:
                tooltip = Indicator.LOGGED_OUT_TEXT
            else:
                tooltip = f"User: {state.user.display_name}"
        self.set_tooltip_text(tooltip)

    def _update_menu_item_streams(self) -> None:
        """Update live streams menu item label and tooltip."""
        state = self._gui_manager.app.state

        with state.locks["validation_info"]:
            logged_out = state.validation_info is None

        label = Indicator.LOGGED_OUT_TEXT
        sensitive = False

        if not logged_out:
            with state.locks["live_streams"]:
                stream_count = len(state.live_streams)
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
        state = self._gui_manager.app.state
        menu = self._menu_streams

        # Order streams by viewer count
        with state.locks["live_streams"]:
            streams = sorted(state.live_streams, key=lambda s: -s.viewer_count)

        # Live streams?
        if streams:
            # Clear menu
            for item in menu.get_children():
                menu.remove(item)

            # Selected streams to top
            if settings.get_boolean("show-selected-channels-on-top"):
                with state.locks["enabled_channel_ids"]:
                    ec_ids = state.enabled_channel_ids.items()
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
