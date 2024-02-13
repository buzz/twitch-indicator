import logging
from copy import deepcopy
from typing import TYPE_CHECKING

from gi.repository import GdkPixbuf, GLib, Notify

from twitch_indicator.api.models import Stream
from twitch_indicator.constants import APP_NAME
from twitch_indicator.gui.cached_profile_image import CachedProfileImage
from twitch_indicator.state import ChannelState
from twitch_indicator.utils import format_viewer_count

if TYPE_CHECKING:
    from twitch_indicator.gui.gui_manager import GuiManager


class Notifications:
    """Keep track of notifications."""

    def __init__(self, gui_manager: "GuiManager") -> None:
        self._logger = logging.getLogger(__name__)
        self._gui_manager = gui_manager
        self._notifications: list[Notify.Notification] = []
        self._live_stream_user_ids: list[int] = []

        Notify.init(APP_NAME)

        self._gui_manager.app.state.add_handler("live_streams", self._update_live_streams)

    def _update_live_streams(self, new_streams: list[Stream]) -> None:
        """Filter live streams for new streams."""
        app = self._gui_manager.app

        with app.state.locks["live_streams"]:
            self._logger.debug("_update_live_streams(): %d streams", len(new_streams))

            # Skip first notification run
            with app.state.locks["first_run"]:
                first_run = app.state.first_run
            if not first_run:
                if app.settings.get_boolean("enable-notifications"):
                    with app.state.locks["enabled_channel_ids"]:
                        ec_ids = app.state.enabled_channel_ids
                        notify_list = [
                            deepcopy(s)
                            for s in new_streams
                            # stream wasn't live before?
                            if s.user_id not in self._live_stream_user_ids
                            # stream is in enabled list?
                            and ec_ids.get(s.user_id, ChannelState.DISABLED) == ChannelState.ENABLED
                        ]
                    GLib.idle_add(self._show_notifications, notify_list)

            self._live_stream_user_ids = [s.user_id for s in new_streams]

    def _show_notifications(self, streams: list[Stream]) -> None:
        """Show notification for streams, passed as a list of dictionaries."""
        self._logger.debug("_show_notifications(): notify %d streams", len(streams))

        settings = self._gui_manager.app.settings
        for stream in streams:
            show_game_playing = settings.get_boolean("show-game-playing")
            show_viewer_count = settings.get_boolean("show-viewer-count")

            msg = f"{stream.user_name} just went LIVE!"
            descr = f"{stream.title}"

            if show_game_playing or show_viewer_count:
                descr += "\n"
                if show_game_playing:
                    descr += f"\nPlaying: <b>{stream.game_name}</b>"
                if show_viewer_count:
                    viewer_count = format_viewer_count(stream.viewer_count)
                    descr += f"\nViewers: <b>{viewer_count}</b>"

            pixbuf = CachedProfileImage.new_from_cached(stream.user_id)

            self._show_notification(msg, descr, stream.user_login, pixbuf)

    def _show_notification(
        self, msg: str, descr: str, user_login: str, pixbuf: GdkPixbuf.Pixbuf
    ) -> None:
        """Show notification and store in list."""
        self._logger.debug("_show_notification(): %s: %s", msg, descr)

        notification = Notify.Notification.new(msg, descr)
        notification.set_category("presence.online")

        # Keep a reference to notifications, otherwise action callback won't work
        self._notifications.append(notification)
        notification.add_action("watch", "Watch", self._on_notification_watch, user_login)
        notification.connect("closed", self._on_closed)

        notification.set_image_from_pixbuf(pixbuf)
        notification.show()

    def _on_closed(self, notification: Notify.Notification) -> None:
        """Called when notification is closed."""
        self._notifications.remove(notification)

    def _on_notification_watch(
        self, notification: Notify.Notification, action: str, user_login: str
    ) -> None:
        """Callback for notification stream watch action."""
        self._gui_manager.app.actions.action_group.activate_action(
            "open-stream", GLib.Variant.new_string(user_login)
        )
