import os
import subprocess
import traceback
import webbrowser
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

from twitch_indicator.constants import CACHE_DIR, TWITCH_WEB_URL

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


def parse_rfc3339_timestamp(rfc3339_timestamp):
    """Parse a Twitch API timestamp which uses nanoseconds instead of milliseconds."""
    timestamp = datetime.strptime(rfc3339_timestamp[:26], "%Y-%m-%dT%H:%M:%S.%f")
    return timestamp.replace(tzinfo=timezone.utc)


def build_stream_url(user_login):
    """Build a Twitch stream URL from username."""
    url_parts = urlparse(TWITCH_WEB_URL)
    return urlunparse(url_parts._replace(path=user_login))


def open_stream(url, open_command):
    """Open URL in browser using either default webbrowser or custom command."""
    browser = webbrowser.get().basename
    formatted = open_command.format(url=url, browser=browser).split()
    subprocess.Popen(formatted)


def coro_exception_handler(fut):
    try:
        exc = fut.exception()
        if exc is not None:
            traceback.print_exception(exc)
    except Exception:
        pass
