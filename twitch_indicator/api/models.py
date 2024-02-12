from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class UserInfo(BaseModel):
    """Twitch API user info."""

    client_id: str
    login: str
    scopes: list[str]
    user_id: int
    expires_in: int


class FollowedChannel(BaseModel):
    """Twitch API followed channel."""

    broadcaster_id: int
    broadcaster_login: str
    broadcaster_name: str
    followed_at: datetime


class Stream(BaseModel):
    """Twitch API live stream."""

    id: int
    user_id: int
    user_login: str
    user_name: str
    game_id: int
    game_name: str
    type: Literal["live"]
    title: str
    viewer_count: int
    started_at: datetime
    language: str
    thumbnail_url: str
    tags: list[str]
