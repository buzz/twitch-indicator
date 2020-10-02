"""Pass Twitch API auth token to indicator via unix socket."""
import os.path
from socket import AF_UNIX, SOCK_DGRAM, socket
import sys

from twitch_indicator.constants import AUTH_SOCKET_PATH


def main():
    """Main entry point."""
    if os.path.exists(AUTH_SOCKET_PATH):
        client = socket(AF_UNIX, SOCK_DGRAM)
        client.connect(AUTH_SOCKET_PATH)
        client.send(sys.argv[1].encode("utf-8"))
        client.close()
