from gi.repository import GdkPixbuf, GLib

from twitch_indicator.constants import (
    FALLBACK_PROFILE_IMAGE_FILENAME,
    FALLBACK_PROFILE_IMAGE_ICON_FILENAME,
)
from twitch_indicator.utils import ImageVariant, get_cached_image_filename, get_data_file


class CachedProfileImage(GdkPixbuf.Pixbuf):
    """Cached channel profile image."""

    @classmethod
    def new_from_cached(cls, user_id: int, variant: ImageVariant = "regular") -> GdkPixbuf.Pixbuf:
        """Create pixbuf from disk cache."""
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(get_cached_image_filename(user_id, variant))
        except GLib.Error:
            filepath = get_data_file(
                FALLBACK_PROFILE_IMAGE_FILENAME
                if variant == "regular"
                else FALLBACK_PROFILE_IMAGE_ICON_FILENAME
            )
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(filepath))

        if pixbuf is None:
            raise RuntimeError("Could not load pixbuf")

        return pixbuf
