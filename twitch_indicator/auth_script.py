"""Pass Twitch API auth token to indicator."""
import os.path
from socket import AF_UNIX, SOCK_DGRAM, socket
import sys


def main():
    """Main entry point."""
    socket_path = os.path.join(os.sep, "tmp", "twitch-indicator-auth-socket")
    if os.path.exists(socket_path):
        client = socket(AF_UNIX, SOCK_DGRAM)
        client.connect(socket_path)
        client.send(sys.argv[1].encode("utf-8"))
        client.close()
