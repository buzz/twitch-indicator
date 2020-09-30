"""Twitch API handling"""

import json
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import urlopen, Request, HTTPError
from gi.repository import GdkPixbuf

from twitch_indicator.constants import (
    DEFAULT_AVATAR,
    TWITCH_API_LIMIT,
    TWITCH_API_URL,
    TWITCH_WEB_URL,
    TWITCH_CLIENT_ID,
)


class TwitchApi:
    """Access Twitch API."""

    channel_info_cache = {}
    game_info_cache = {}

    def __init__(self, token):
        self.token = token

    def clear_cache(self):
        """Clear channel info and game info cache."""
        self.channel_info_cache.clear()
        self.game_info_cache.clear()

    def fetch_followed_channels(self, user_id):
        """Fetch user followed channels and return a list with channel ids."""
        url = self.build_url("users/follows", {"from_id": user_id})
        resp = self.get_api_decoded_response(url)
        if isinstance(resp, HTTPError):
            return resp

        total = int(resp["total"])
        fetched = len(resp["data"])
        data = resp["data"]

        # User has not followed any channels
        if total == 0:
            return None

        last = resp
        while fetched < total:
            url = self.build_url(
                "users/follows",
                {"after": last["pagination"]["cursor"], "from_id": user_id},
            )
            nxt = self.get_api_decoded_response(url)
            if isinstance(nxt, HTTPError):
                return nxt

            fetched += len(nxt["data"])
            data += nxt["data"]
            last = nxt

        return [data["to_id"] for data in data]

    def fetch_live_streams(self, channel_ids):
        """Fetches live streams data from Twitch, and returns as list of
        dictionaries.
        """
        channel_index = 0
        channel_max = TWITCH_API_LIMIT
        channels_live = []

        while channel_index < len(channel_ids):
            curr_channels = channel_ids[channel_index:channel_max]
            channel_index += len(curr_channels)
            channel_max += TWITCH_API_LIMIT

            params = [("user_id", user_id) for user_id in curr_channels]
            url = self.build_url("streams", params)
            resp = self.get_api_decoded_response(url)

            for channel in resp["data"]:
                channels_live.append(channel)

        streams = []
        for stream in channels_live:
            channel_info = self.get_channel_info(stream["user_id"])
            game_info = self.get_game_info(stream["game_id"])

            channel_image = urlopen(
                channel_info["profile_image_url"]
                if channel_info["profile_image_url"]
                else DEFAULT_AVATAR
            )
            image_loader = GdkPixbuf.PixbufLoader.new()
            image_loader.set_size(128, 128)
            image_loader.write(channel_image.read())
            image_loader.close()

            stream = {
                "name": channel_info["display_name"],
                "game": game_info["name"],
                "title": stream["title"],
                "image": channel_info["profile_image_url"],
                "pixbuf": image_loader,
                "url": f"{TWITCH_WEB_URL}{channel_info['login']}",
            }
            streams.append(stream)

        return streams

    def get_channel_info(self, channel_id):
        """Get channel info."""
        channel_info = self.channel_info_cache.get(int(channel_id))
        if channel_info is not None:
            return channel_info

        url = self.build_url("users", {"id": channel_id})
        resp = self.get_api_decoded_response(url)
        if isinstance(resp, HTTPError):
            return resp
        if not len(resp["data"]) == 1:
            return None

        self.channel_info_cache[int(channel_id)] = resp["data"][0]
        return resp["data"][0]

    def get_game_info(self, game_id):
        """Get game info."""
        game_info = self.game_info_cache.get(int(game_id))
        if game_info is not None:
            return game_info

        url = self.build_url("games", {"id": game_id})
        resp = self.get_api_decoded_response(url)
        if isinstance(resp, HTTPError):
            return resp
        if not len(resp["data"]) == 1:
            return None

        self.game_info_cache[int(game_id)] = resp["data"][0]
        return resp["data"][0]

    def get_user_id(self, username):
        """Get Twitch user ID."""
        url = self.build_url("users", {"login": username})
        resp = self.get_api_decoded_response(url)
        if isinstance(resp, HTTPError):
            return resp
        if not len(resp["data"]) == 1:
            return None
        return resp["data"][0]["id"]

    @staticmethod
    def build_url(loc, params):
        """Construct API URL."""
        url_parts = list(urlparse(TWITCH_API_URL))
        url_parts[2] += loc
        url_parts[4] = urlencode(params)
        return urlunparse(url_parts)

    def get_api_decoded_response(self, url):
        """Decode JSON API response."""
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {self.token}",
        }
        req = Request(url, headers=headers)
        try:
            resp = urlopen(req).read()
            decoded = json.loads(resp)
            return decoded
        except HTTPError as err:
            return err
