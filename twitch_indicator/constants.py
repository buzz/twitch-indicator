import os.path
from gi.repository import GLib

VERSION = "1.6"

TWITCH_WEB_URL = "https://www.twitch.tv/"
TWITCH_API_URL = "https://api.twitch.tv/helix/"
TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/authorize"
TWITCH_AUTH_REDIRECT_URI = "http://localhost:17563"
TWITCH_AUTH_SCOPES = ["user:read:follows"]
TWITCH_CLIENT_ID = "vrulzk2tm1ozo2c1iv5a14m1ohbill"
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
