import os
from random import SystemRandom
from socket import AF_UNIX, SOCK_DGRAM, socket
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
import webbrowser

from gi.repository import GLib, Gtk

from twitch_indicator.constants import (
    AUTH_SOCKET_PATH,
    AUTH_TOKEN_PATH,
    CONFIG_DIR,
    TWITCH_AUTH_REDIRECT_URI,
    TWITCH_AUTH_URL,
    TWITCH_AUTH_SCOPES,
    TWITCH_CLIENT_ID,
    UNICODE_ASCII_CHARACTER_SET,
)
from twitch_indicator.util import get_data_filepath


class Auth:
    """Handle API auth token."""

    def __init__(self, app):
        self.app = app
        self.token = None
        self.ensure_config_dir()
        self.restore_token()

    @staticmethod
    def ensure_config_dir():
        """Create config dir if it doesn't exists."""
        if not os.path.isdir(CONFIG_DIR):
            os.mkdir(CONFIG_DIR)

    def restore_token(self):
        """Restore auth token from config dir."""
        if os.path.isfile(AUTH_TOKEN_PATH):
            with open(AUTH_TOKEN_PATH, "r", encoding="UTF-8") as token_file:
                self.token = token_file.read()

    def acquire_token(self):
        """Aquire Twitch API auth token."""
        redirect_uri_parts = urlparse(TWITCH_AUTH_REDIRECT_URI)
        rand = SystemRandom()
        state = "".join(rand.choice(UNICODE_ASCII_CHARACTER_SET) for x in range(30))
        url_parts = list(urlparse(TWITCH_AUTH_URL))
        query = {
            "response_type": "token",
            "client_id": TWITCH_CLIENT_ID,
            "state": state,
            "redirect_uri": TWITCH_AUTH_REDIRECT_URI,
            "scope": " ".join(TWITCH_AUTH_SCOPES),
        }
        url_parts[4] = urlencode(query)
        url = urlunparse(url_parts)

        # Listen on socket
        server = socket(AF_UNIX, SOCK_DGRAM)
        if os.path.exists(AUTH_SOCKET_PATH):
            os.remove(AUTH_SOCKET_PATH)
        server.bind(AUTH_SOCKET_PATH)
        os.chmod(AUTH_SOCKET_PATH, 0o700)

        # Open Twich auth URL
        webbrowser.open_new_tab(url)

        # Receive auth token via auth_script.py
        datagram = server.recv(1024)
        received = datagram.decode("utf-8")
        server.close()
        os.remove(AUTH_SOCKET_PATH)

        # Check response
        response_url_parts = urlparse(received)
        assert response_url_parts[0] == redirect_uri_parts[0]
        assert response_url_parts[1] == redirect_uri_parts[1]
        hash_params = parse_qs(response_url_parts[5])
        assert hash_params["token_type"][0] == "bearer"
        assert hash_params["state"][0] == state
        [self.token] = hash_params["access_token"]

        # Save token to disk
        with open(AUTH_TOKEN_PATH, "w", encoding="UTF-8") as token_file:
            token_file.write(self.token)
        os.chmod(AUTH_TOKEN_PATH, 0o600)

    def show_dialog(self):
        """Show authentication dialog."""
        dialog = Gtk.Dialog("Twitch authentication", None, 0)
        dialog.add_buttons(
            Gtk.STOCK_QUIT, Gtk.ResponseType.CANCEL, "Authorize", Gtk.ResponseType.OK
        )
        dialog.set_position(Gtk.WindowPosition.CENTER)

        builder = Gtk.Builder()
        builder.add_from_file(get_data_filepath("twitch-indicator-auth.glade"))

        box = dialog.get_content_area()
        box.add(builder.get_object("grid"))

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            try:
                self.acquire_token()
            finally:
                dialog.destroy()
                GLib.idle_add(self.app.start_api_thread)
        else:
            self.app.quit()
