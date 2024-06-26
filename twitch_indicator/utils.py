import os
import traceback
from concurrent.futures import CancelledError, Future
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any, Literal, Mapping, Optional, Sequence, cast
from urllib.parse import urlencode, urlparse, urlunparse

from twitch_indicator.constants import CACHE_DIR, TWITCH_API_URL, TWITCH_WEB_URL

_ROOT = os.path.abspath(os.path.dirname(__file__))

ParamVal = str | int
Params = Mapping[str, ParamVal | Sequence[ParamVal]]
ImageVariant = Literal["regular", "icon"]


def get_data_file(filename: str) -> os.PathLike[str]:
    """Get resource data file."""
    return cast(os.PathLike[str], files("twitch_indicator.data").joinpath(filename))


def get_cached_image_filename(user_id: int, variant: ImageVariant = "regular") -> str:
    """Get cached image file name."""
    append = "" if variant == "regular" else "_icon"
    return os.path.join(CACHE_DIR, f"{user_id}{append}")


def format_viewer_count(count: int) -> str:
    """Format viewer count."""
    if count > 1000:
        return f"{round(count / 1000)} K"
    return str(count)


def parse_rfc3339_timestamp(rfc3339_timestamp: str) -> datetime:
    """Parse a Twitch API timestamp which uses nanoseconds instead of milliseconds."""
    timestamp = datetime.strptime(rfc3339_timestamp[:26], "%Y-%m-%dT%H:%M:%S.%f")
    return timestamp.replace(tzinfo=timezone.utc)


def build_stream_url(user_login: str) -> str:
    """Build a Twitch stream URL from username."""
    url_parts = urlparse(TWITCH_WEB_URL)
    return urlunparse(url_parts._replace(path=user_login))


def build_api_url(
    path_append: Optional[str] = None,
    params: Optional[Params] = None,
    url: str = TWITCH_API_URL,
) -> str:
    """Build a Twitch API URL."""
    url_parts = urlparse(url)
    if path_append is not None:
        url_parts = url_parts._replace(path=url_parts.path + path_append)
    if params:
        url_parts = url_parts._replace(query=urlencode(params, doseq=True))
    return urlunparse(url_parts)


def coro_exception_handler(fut: Future[Any]) -> None:
    try:
        exc = fut.exception()
        if exc is not None:
            traceback.print_exception(exc)
    except CancelledError:
        pass
