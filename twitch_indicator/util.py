import os

from twitch_indicator.constants import CACHE_DIR

_ROOT = os.path.abspath(os.path.dirname(__file__))


def get_data_filepath(path):
    """Return package data file path."""
    return os.path.join(_ROOT, "data", path)


def get_image_filename(user_id):
    """Get cached image file name."""
    return os.path.join(CACHE_DIR, f"{user_id}.png")


def format_viewer_count(count):
    """Format viewer count."""
    if count > 1000:
        return f"{round(count / 1000)} K"
    return count
