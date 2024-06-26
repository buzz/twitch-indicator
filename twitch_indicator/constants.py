import os.path

from gi.repository import GLib

APP_NAME = "Twitch Indicator"
VERSION = "1.8"

TWITCH_WEB_URL = "https://www.twitch.tv/"
TWITCH_API_URL = "https://api.twitch.tv/helix/"
TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/"
TWITCH_AUTH_REDIRECT_URI = "http://localhost:17563"
TWITCH_AUTH_SCOPES = ["user:read:follows"]
TWITCH_CLIENT_ID = "vrulzk2tm1ozo2c1iv5a14m1ohbill"
TWITCH_PAGE_SIZE = 100
TWITCH_VALIDATION_INTERVAL = 3600  # 1h

APP_ID = "org.buzz.twitch-indicator"
SETTINGS_KEY = "apps.twitch-indicator"
UNICODE_ASCII_CHARACTER_SET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "twitch-indicator")
CACHE_DIR = os.path.join(
    os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "twitch-indicator"
)
AUTH_TOKEN_PATH = os.path.join(CONFIG_DIR, "authtoken")
TWITCH_LOGO_FILENAME = "twitch_logo.png"
TWITCH_LOGO_ICON_FILENAME = "twitch_logo_icon.png"
REFRESH_INTERVAL_LIMITS = (0.5, 15)
