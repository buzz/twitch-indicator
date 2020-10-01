"""Notifications"""

from gi.repository import Notify


class Notifications:
    """Keep track of notifications."""

    def __init__(self):
        Notify.init("Twitch Indicator")
        self.notifications = []

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

    def on_closed(self, notification):
        """Called when notification is closed."""
        self.notifications.remove(notification)
