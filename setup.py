#!/usr/bin/env python3
from distutils.core import setup

setup(name='twitch-indicator',
      version='0.30',
      description='Twitch.tv indicator for Linux. Tracks your followed channels and notifies when they go live.',
      author='buzz',
      author_email='buzz-AT-l4m1-DOT-de',
      license='ZLIB',
      url='https://github.com/buzz/twitch-indicator',
      scripts=['twitch-indicator.py'],
      data_files=[
          ('share/applications', ['twitch-indicator.desktop']),
          ('share/icons', ['twitch-indicator.svg']),
          ('share/glib-2.0/schemas', ['apps.twitch-indicator.gschema.xml']),
          ('share/twitch-indicator', ['twitch-indicator.glade']),
      ],
)
