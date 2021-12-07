from urllib.request import urlopen
import os
import time
from gi.repository import GdkPixbuf, GLib

from twitch_indicator.constants import PROFILE_IMAGE_SIZE, CACHE_DIR


class CachedProfileImage(GdkPixbuf.Pixbuf):
    """Cached channel profile image."""

    @staticmethod
    def ensure_cache_dir():
        """Create cache dir if it doesn't exists."""
        if not os.path.isdir(CACHE_DIR):
            os.mkdir(CACHE_DIR)

    @staticmethod
    def get_filename(channel_id):
        """Get cached image file name."""
        return os.path.join(CACHE_DIR, f"{channel_id}.png")

    @classmethod
    def new_from_cached(cls, channel_id):
        """Create pixbuf from disk cache."""
        return GdkPixbuf.Pixbuf.new_from_file(cls.get_filename(channel_id))

    @classmethod
    def new_from_profile_url(cls, channel_id, url):
        """Create pixbuf from disk cache or remote URL, cache and return icon size."""
        cls.ensure_cache_dir()
        filename = cls.get_filename(channel_id)

        # Try file cache
        try:
            time_diff = os.path.getmtime(filename) - time.time()
            if time_diff < 3 * 24 * 60 * 60:  # 3 days
                return GdkPixbuf.Pixbuf.new_from_file(filename)
        except (FileNotFoundError, GLib.Error):
            # Load from URL
            with urlopen(url) as response:
                data = response.read()
            pixbuf_loader = GdkPixbuf.PixbufLoader.new()
            pixbuf_loader.write(data)
            pixbuf_loader.close()
            pixbuf = pixbuf_loader.get_pixbuf()

            # Save scaled-down version to disk
            pixbuf_cache = pixbuf.copy()
            pixbuf_cache.scale_simple(
                *PROFILE_IMAGE_SIZE, GdkPixbuf.InterpType.BILINEAR
            )
            pixbuf_cache.savev(filename, "png", (), ())

        # Create menu icon
        pixbuf.scale_simple(32, 32, GdkPixbuf.InterpType.BILINEAR)

        return pixbuf
