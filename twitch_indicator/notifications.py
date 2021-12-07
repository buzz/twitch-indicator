import webbrowser
import os

from gi.repository import Notify

from twitch_indicator.util import format_viewer_count


class Notifications:
    """Keep track of notifications."""

    def __init__(self, settings):
        self.settings = settings
        Notify.init("Twitch Indicator")
        self.notifications = []
        # Avoid initial notification spam
        self.first_notification_run = True

    def show(self, msg, descr, action=None, category="", image=None):
        """Show notification and store in list."""
        notification = Notify.Notification.new(msg, descr, category)

        if image:
            notification.set_image_from_pixbuf(image)

        if action:
            # Keep a reference to notifications, otherwise action callback won't work
            self.notifications.append(notification)
            notification.add_action(*action)
            notification.connect("closed", self.on_closed)

        notification.show()

    def show_streams(self, streams):
        """Show notification for streams, passed as a list of dictionaries."""
        if not self.first_notification_run:
            for stream in streams:
                show_game_playing = self.settings.get_boolean("show-game-playing")
                show_viewer_count = self.settings.get_boolean("show-viewer-count")

                msg = f"{stream['name']} just went LIVE!"
                descr = f"{stream['title']}"

                if show_game_playing or show_viewer_count:
                    descr += "\n"
                    if show_game_playing:
                        descr += f"\nPlaying: <b>{stream['game']}</b>"
                    if show_viewer_count:
                        viewer_count = format_viewer_count(stream["viewer_count"])
                        descr += f"\nViewers: <b>{viewer_count}</b>"

                action = (
                    "watch",
                    "Watch",
                    self.on_notification_watch,
                    stream["url"],
                )
                self.show(
                    msg,
                    descr,
                    action=action,
                    category="presence.online",
                    image=stream["pixbuf"].get_pixbuf(),
                )
        else:
            self.first_notification_run = False

    def on_closed(self, notification):
        """Called when notification is closed."""
        self.notifications.remove(notification)

    def on_notification_watch(self, _, __, url):
        """Callback for notification stream watch action."""
        browser = webbrowser.get().basename
        cmd = self.settings.get_string("open-command")
        os.system(cmd.format(url=url, browser=browser))
