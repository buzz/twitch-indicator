import os

_ROOT = os.path.abspath(os.path.dirname(__file__))


def get_data_filepath(path):
    """Return package data file path."""
    return os.path.join(_ROOT, "data", path)


def format_viewer_count(count):
    """Format viewer count."""
    if count > 1000:
        return f"{round(count / 1000)} K"
    return count
