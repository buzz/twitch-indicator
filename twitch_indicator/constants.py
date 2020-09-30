"""Constants"""
import os.path
from gi.repository import GLib

VERSION = "0.29"

TWITCH_BASE_URL = "https://www.twitch.tv/"
TWITCH_API_URL = "https://api.twitch.tv/helix/"
TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/authorize"
TWITCH_AUTH_REDIRECT_URI = "twitch-tray-icon-app://authorize"
TWITCH_CLIENT_ID = "lp42a3ot0vosrva84upd4up077f6vd"
DEFAULT_AVATAR = (
    "http://static-cdn.jtvnw.net/jtv_user_pictures/xarth/404_user_150x150.png"
)
SETTINGS_KEY = "apps.twitch-indicator"
UNICODE_ASCII_CHARACTER_SET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "twitch-indicator")
