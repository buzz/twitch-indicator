import os.path
from gi.repository import GLib

VERSION = "1.5"

TWITCH_WEB_URL = "https://www.twitch.tv/"
TWITCH_API_URL = "https://api.twitch.tv/helix/"
TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/authorize"
TWITCH_AUTH_REDIRECT_URI = "twitch-indicator-auth://authorize"
TWITCH_AUTH_SCOPES = "user:read:email"
TWITCH_CLIENT_ID = "lp42a3ot0vosrva84upd4up077f6vd"
TWITCH_API_LIMIT = 100
DEFAULT_AVATAR = (
    "http://static-cdn.jtvnw.net/jtv_user_pictures/xarth/404_user_150x150.png"
)

SETTINGS_KEY = "apps.twitch-indicator"
UNICODE_ASCII_CHARACTER_SET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "twitch-indicator")
CACHE_DIR = os.path.join(
    os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "twitch-indicator"
)
PROFILE_IMAGE_SIZE = 120, 120
AUTH_TOKEN_PATH = os.path.join(CONFIG_DIR, "authtoken")
AUTH_SOCKET_PATH = os.path.join(os.sep, "tmp", "twitch-indicator-auth-socket")
