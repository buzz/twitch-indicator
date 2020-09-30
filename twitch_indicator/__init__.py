"""Twitch indicator package."""

import os

_ROOT = os.path.abspath(os.path.dirname(__file__))


def get_data_filepath(path):
    """Return package data file path."""
    return os.path.join(_ROOT, "data", path)
