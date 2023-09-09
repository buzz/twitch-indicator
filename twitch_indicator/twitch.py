import json
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import urlopen, Request, HTTPError

from twitch_indicator.cached_profile_image import CachedProfileImage
from twitch_indicator.constants import (
    DEFAULT_AVATAR,
    TWITCH_API_LIMIT,
    TWITCH_API_URL,
    TWITCH_WEB_URL,
    TWITCH_CLIENT_ID,
)
from twitch_indicator.errors import NotAuthorizedException


class TwitchApi:
    """Access Twitch API."""

    def __init__(self, auth):
        self.auth = auth
        self.channel_info_cache = {}
        self.game_info_cache = {}

    def clear_cache(self):
        """Clear channel info and game info cache."""
        self.channel_info_cache.clear()
        self.game_info_cache.clear()

    def fetch_followed_channels(self, user_id):
        """Fetch user followed channels and return a list with channel ids."""
        loc = "channels/followed"
        url = self.build_url(loc, {"user_id": user_id})
        resp = self.get_api_response(url)

        total = int(resp["total"])
        fetched = len(resp["data"])
        data = resp["data"]

        # User has not followed any channels
        if total == 0:
            return None

        last = resp
        while fetched < total:
            url = self.build_url(
                loc,
                {"after": last["pagination"]["cursor"], "user_id": user_id},
            )
            nxt = self.get_api_response(url)

            fetched += len(nxt["data"])
            data += nxt["data"]
            last = nxt

        return [{"id": int(data["broadcaster_id"]), "name": data["broadcaster_name"]} for data in data]

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
            resp = self.get_api_response(url)

            for channel in resp["data"]:
                channels_live.append(channel)

        streams = []
        for stream in channels_live:
            user_id = int(stream["user_id"])
            channel_info = self.get_channel_info(user_id)
            try:
                game_info = self.get_game_info(int(stream["game_id"]))
            except ValueError:
                game_info = {"name": ""}

            stream = {
                "id": user_id,
                "name": channel_info["display_name"],
                "game": game_info["name"],
                "title": stream["title"],
                "image": channel_info["profile_image_url"],
                "pixbuf": channel_info["pixbuf"],
                "url": f"{TWITCH_WEB_URL}{channel_info['login']}",
                "viewer_count": stream["viewer_count"],
            }
            streams.append(stream)

        return streams

    def get_channel_info(self, channel_id):
        """Get channel info."""
        try:
            return self.channel_info_cache[channel_id]
        except KeyError:
            url = self.build_url("users", {"id": channel_id})
            resp = self.get_api_response(url)
            if not len(resp["data"]) == 1:
                return ValueError("Bad API response.")
            channel_info = resp["data"][0]

            # Channel image
            if channel_info["profile_image_url"]:
                channel_info["pixbuf"] = CachedProfileImage.new_from_profile_url(
                    channel_id, channel_info["profile_image_url"]
                )
            else:
                channel_info["pixbuf"] = CachedProfileImage.new_from_profile_url(
                    "default", DEFAULT_AVATAR
                )

            self.channel_info_cache[channel_id] = channel_info
            return channel_info

    def get_game_info(self, game_id):
        """Get game info."""
        try:
            return self.game_info_cache[game_id]
        except KeyError:
            url = self.build_url("games", {"id": game_id})
            resp = self.get_api_response(url)
            if not len(resp["data"]) == 1:
                return ValueError("Bad API response.")
            self.game_info_cache[game_id] = resp["data"][0]
            return resp["data"][0]

    def get_user_id(self):
        """Get Twitch user ID."""
        url = self.build_url("users")
        resp = self.get_api_response(url)
        if not len(resp["data"]) == 1:
            return ValueError("Bad API response.")
        return int(resp["data"][0]["id"])

    @staticmethod
    def build_url(loc, params=None):
        """Construct API URL."""
        url_parts = list(urlparse(TWITCH_API_URL))
        url_parts[2] += loc
        if params:
            url_parts[4] = urlencode(params)
        return urlunparse(url_parts)

    def get_api_response(self, url):
        """Decode JSON API response."""
        if not self.auth.token:
            raise NotAuthorizedException
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {self.auth.token}",
        }
        req = Request(url, headers=headers)
        try:
            with urlopen(req) as response:
                return json.loads(response.read())
        except HTTPError as err:
            if err.code == 401:
                raise NotAuthorizedException from err
            raise err
