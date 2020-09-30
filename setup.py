#!/usr/bin/env python3
from distutils.core import setup

# parse version (setup.py should not import module!)
def get_version():
    """Get version using regex parsing."""
    versionfile = "twitch_indicator/constants.py"
    with open(versionfile, "rt") as file:
        version_file_content = file.read()
    match = re.search(r"^VERSION = ['\"]([^'\"]*)['\"]", version_file_content, re.M)
    if match:
        return match.group(1)
    raise RuntimeError("Unable to find version string in {}.".format(versionfile))


setup(
    name="twitch-indicator",
    version=get_version(),
    description="Twitch.tv indicator for Linux. Tracks your followed channels and notifies when they go live.",
    author="buzz",
    author_email="buzz@users.noreply.github.com",
    license="GPLv2",
    url="https://github.com/buzz/twitch-indicator",
    scripts=["twitch-indicator.py"],
    data_files=[
        ("share/applications", ["twitch-indicator.desktop"]),
        ("share/icons", ["twitch-indicator.svg"]),
        ("share/glib-2.0/schemas", ["apps.twitch-indicator.gschema.xml"]),
        ("share/twitch-indicator", ["twitch-indicator.glade"]),
    ],
)
