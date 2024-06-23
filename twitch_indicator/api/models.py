from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class ValidationInfo(BaseModel):
    """Twitch API validation info."""

    client_id: str
    login: str
    scopes: list[str]
    user_id: int
    expires_in: int


class User(BaseModel):
    """Twitch API user info."""

    id: int
    login: str
    display_name: str
    type: Literal["admin", "global_mod", "staff", ""]
    broadcaster_type: Literal["affiliate", "partner", ""]
    description: str
    profile_image_url: str
    offline_image_url: str
    view_count: int
    created_at: datetime


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
    game_id: Optional[int]
    game_name: str
    type: Literal["live"]
    title: str
    viewer_count: int
    started_at: datetime
    language: str
    thumbnail_url: str
    tags: Optional[list[str]]  # Might be None contrary to the API doc!

    @field_validator("game_id", mode="before")
    @classmethod
    def allow_empty(cls, value: str) -> Optional[int]:
        """Map empty strings to `None`."""
        try:
            return int(value)
        except ValueError:
            if value == "":
                return None
            raise
