from gi.repository import GdkPixbuf

from twitch_indicator.util import get_image_filename


class CachedProfileImage(GdkPixbuf.Pixbuf):
    """Cached channel profile image."""

    @classmethod
    def new_from_cached(cls, channel_id):
        """Create pixbuf from disk cache."""
        return GdkPixbuf.Pixbuf.new_from_file(get_image_filename(channel_id))
