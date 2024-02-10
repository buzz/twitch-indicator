import logging

from gi.repository import GLib, Notify

from twitch_indicator.gui.cached_profile_image import CachedProfileImage
from twitch_indicator.util import build_stream_url, format_viewer_count, open_stream


class Notifications:
    """Keep track of notifications."""

    def __init__(self, gui_manager):
        self._logger = logging.getLogger(__name__)
        self._gui_manager = gui_manager
        self._notifications = []

        Notify.init("Twitch Indicator")

        self._gui_manager.app.state.add_handler(
            "add_live_streams", self._stream_notification
        )

    def _stream_notification(self, streams):
        """Show notification for streams, passed as a list of dictionaries."""
        settings = self._gui_manager.app.settings
        for stream in streams:
            show_game_playing = settings.get_boolean("show-game-playing")
            show_viewer_count = settings.get_boolean("show-viewer-count")

            msg = f"{stream['name']} just went LIVE!"
            descr = f"{stream['title']}"

            if show_game_playing or show_viewer_count:
                descr += "\n"
                if show_game_playing:
                    descr += f"\nPlaying: <b>{stream['game']}</b>"
                if show_viewer_count:
                    viewer_count = format_viewer_count(stream["viewer_count"])
                    descr += f"\nViewers: <b>{viewer_count}</b>"

            try:
                pixbuf = CachedProfileImage.new_from_cached(stream["id"])
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

            self._logger.debug(
                f"_stream_notification(): Showing notification for {stream['user_id']}"
            )
            self._show_notification(
                msg,
                descr,
                action=action,
                category="presence.online",
                pixbuf=pixbuf,
            )

    def _show_notification(self, msg, descr, action=None, category="", pixbuf=None):
        """Show notification and store in list."""
        notification = Notify.Notification.new(msg, descr, category)

        if pixbuf:
            notification.set_image_from_pixbuf(pixbuf)

        if action:
            # Keep a reference to notifications, otherwise action callback won't work
            self._notifications.append(notification)
            notification.add_action(*action)
            notification.connect("closed", self._on_closed)

        notification.show()

    def _on_closed(self, notification):
        """Called when notification is closed."""
        self._notifications.remove(notification)

    def _on_notification_watch(self, _, __, url):
        """Callback for notification stream watch action."""
        open_cmd = self._gui_manager.app.settings.get_string("open-command")
        open_stream(url, open_cmd)
