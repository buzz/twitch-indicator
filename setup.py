#!/usr/bin/env python3
"""setup.py for twitch-indicator"""

import re
from setuptools import find_packages, setup


# parse version (setup.py should not import module!)
def get_version():
    """Get version using regex parsing."""
    versionfile = "twitch_indicator/constants.py"
    with open(versionfile, "rt") as file:
        version_file_content = file.read()
    match = re.search(r"^VERSION = ['\"]([^'\"]*)['\"]", version_file_content, re.M)
    if match:
        return match.group(1)
    raise RuntimeError(f"Unable to find version string in {versionfile}.")


setup(
    name="twitch-indicator",
    version=get_version(),
    description=(
        "Twitch.tv indicator for Linux. "
        "Tracks your followed channels and notifies when they go live."
    ),
    author="buzz",
    author_email="buzz@users.noreply.github.com",
    license="GPLv2",
    url="https://github.com/buzz/twitch-indicator",
    packages=find_packages(),
    entry_points={
        "gui_scripts": ["twitch-indicator = twitch_indicator.__main__:main"],
    },
    data_files=[
        (
            "share/applications",
            ["data/twitch-indicator.desktop"],
        ),
        ("share/icons", ["twitch_indicator/data/twitch-indicator.svg"]),
        ("share/glib-2.0/schemas", ["data/apps.twitch-indicator.gschema.xml"]),
    ],
    package_data={"twitch_indicator": ["data/*"]},
    install_requires=["aiofiles", "aiohttp", "PyGObject"],
)
