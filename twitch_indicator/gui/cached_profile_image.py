from gi.repository import GdkPixbuf, GLib

from twitch_indicator.constants import FALLBACK_PROFILE_IMAGE_FILENAME
from twitch_indicator.utils import get_cached_image_filename, get_data_filepath


class CachedProfileImage(GdkPixbuf.Pixbuf):
    """Cached channel profile image."""

    @classmethod
    def new_from_cached(cls, channel_id: int) -> GdkPixbuf.Pixbuf:
        """Create pixbuf from disk cache."""
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(
                get_cached_image_filename(channel_id)
            )
        except GLib.Error:
            filepath = get_data_filepath(FALLBACK_PROFILE_IMAGE_FILENAME)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(filepath)

        if pixbuf is None:
            raise RuntimeError("Could not load pixbuf")

        return pixbuf
