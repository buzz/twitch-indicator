import logging

from gi.repository import GLib, Notify

from twitch_indicator.constants import APP_NAME
from twitch_indicator.gui.cached_profile_image import CachedProfileImage
from twitch_indicator.util import build_stream_url, format_viewer_count, open_stream


class Notifications:
    """Keep track of notifications."""

    NOTIFICATION_KEYS = (
        "user_id",
        "user_name",
        "user_login",
        "title",
        "game_name",
        "viewer_count",
    )

    def __init__(self, gui_manager):
        self._logger = logging.getLogger(__name__)
        self._gui_manager = gui_manager
        self._notifications = []
        self._live_stream_user_ids = []
        self._first_run = True

        Notify.init(APP_NAME)

        self._gui_manager.app.state.add_handler(
            "live_streams", self._update_live_streams
        )

    def _update_live_streams(self, new_streams):
        """Filter live streams for new streams."""
        app = self._gui_manager.app

        with app.state.locks["live_streams"]:
            self._logger.debug(f"_update_live_streams(): {len(new_streams)} streams")

            # Skip first notification run
            if self._first_run:
                self._first_run = False

            else:
                if app.settings.get_boolean("enable-notifications"):
                    with app.state.locks["enabled_channel_ids"]:
                        enabled_channel_ids = app.state.enabled_channel_ids
                        notify_list = [
                            {key: s[key] for key in Notifications.NOTIFICATION_KEYS}
                            for s in new_streams
                            # stream wasn't live before?
                            if s["user_id"] not in self._live_stream_user_ids
                            # stream is in enabled list?
                            and enabled_channel_ids.get(s["user_id"], "0") == "1"
                        ]
                    GLib.idle_add(self._show_notifications, notify_list)

            self._live_stream_user_ids = [s["user_id"] for s in new_streams]

    def _show_notifications(self, streams):
        """Show notification for streams, passed as a list of dictionaries."""
        self._logger.debug(f"_show_notifications(): notify {len(streams)} streams")

        settings = self._gui_manager.app.settings
        for stream in streams:
            show_game_playing = settings.get_boolean("show-game-playing")
            show_viewer_count = settings.get_boolean("show-viewer-count")

            msg = f"{stream['user_name']} just went LIVE!"
            descr = f"{stream['title']}"

            if show_game_playing or show_viewer_count:
                descr += "\n"
                if show_game_playing:
                    descr += f"\nPlaying: <b>{stream['game_name']}</b>"
                if show_viewer_count:
                    viewer_count = format_viewer_count(stream["viewer_count"])
                    descr += f"\nViewers: <b>{viewer_count}</b>"

            try:
                pixbuf = CachedProfileImage.new_from_cached(stream["user_id"])
            except GLib.Error:
                self._logger.warn(
                    f"_stream_notification(): No profile image for {stream['user_id']}"
                )
                pixbuf = None

            action = (
                "watch",
                "Watch",
                self._on_notification_watch,
                build_stream_url(stream["user_login"]),
            )

            self._show_notification(
                msg,
                descr,
                action=action,
                category="presence.online",
                pixbuf=pixbuf,
            )

    def _show_notification(self, msg, descr, action=None, category=None, pixbuf=None):
        """Show notification and store in list."""
        self._logger.debug(f"_show_notification(): {msg}: {descr}")

        notification = Notify.Notification.new(msg, descr)

        if action is not None:
            # Keep a reference to notifications, otherwise action callback won't work
            self._notifications.append(notification)
            notification.add_action(*action)
            notification.connect("closed", self._on_closed)

        if category is not None:
            notification.set_category(category)

        if pixbuf is not None:
            notification.set_image_from_pixbuf(pixbuf)

        notification.show()

    def _on_closed(self, notification):
        """Called when notification is closed."""
        self._notifications.remove(notification)

    def _on_notification_watch(self, _, __, url):
        """Callback for notification stream watch action."""
        open_cmd = self._gui_manager.app.settings.get_string("open-command")
        open_stream(url, open_cmd)
