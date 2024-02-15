from gi.repository import GdkPixbuf, GLib

from twitch_indicator.constants import (
    TWITCH_LOGO_FILENAME,
    TWITCH_LOGO_ICON_FILENAME,
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
            pixbuf = cls.new_app_image()

        if pixbuf is None:
            raise RuntimeError("Could not load pixbuf")

        return pixbuf

    @classmethod
    def new_app_image(cls, variant: ImageVariant = "regular") -> GdkPixbuf.Pixbuf:
        """Create fallback app image."""
        filepath = get_data_file(
            TWITCH_LOGO_FILENAME if variant == "regular" else TWITCH_LOGO_ICON_FILENAME
        )
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(filepath))

        if pixbuf is None:
            raise RuntimeError("Could not load pixbuf")

        return pixbuf
