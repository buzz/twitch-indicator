#!/usr/bin/env python3

import threading
import webbrowser
import json
from urllib.request import urlopen
import gi

gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
gi.require_version('Gtk', '3.0')
from gi.repository import AppIndicator3 as appindicator  # noqa: E402
from gi.repository import GLib, Gio, Notify, GdkPixbuf  # noqa: E402
from gi.repository import Gtk as gtk  # noqa: E402

TWITCH_BASE_URL = 'https://www.twitch.tv/'
TWITCH_API_URL = 'https://api.twitch.tv/kraken/'
DEFAULT_AVATAR = ('http://static-cdn.jtvnw.net/'
                  'jtv_user_pictures/xarth/404_user_150x150.png')
CLIENT_ID = 'oe77z9pq798tln7ngil0exwr0mun4hj'


class Twitch:
    def fetch_followed_channels(self, username):
        """Fetch user followed channels and return a list with channel
        names.
        """
        try:
            self.followed_channels = []

            self.f = urlopen(
                f'{TWITCH_API_URL}users/{username}/follows/channels'
                f'?client_id={CLIENT_ID}&direction=DESC'
                '&limit=100&offset=0&sortby=created_at')
            self.data = json.loads(self.f.read())

            # Return 404 if user does not exist
            try:
                if (self.data['status'] == 404):
                    return 404
            except KeyError:
                pass

            self.pages = int((self.data['_total'] - 1) / 100)
            for page in range(self.pages + 1):
                if page != 0:
                    self.f = urlopen(
                        f'{TWITCH_API_URL}users/{username}/follows/channels'
                        f'?client_id={CLIENT_ID}&direction=DESC&limit=100&'
                        f'offset={page * 100}&sortby=created_at')
                    self.data = json.loads(self.f.read())

                for channel in self.data['follows']:
                    self.followed_channels.append(channel['channel']['name'])

            return self.followed_channels
        except IOError:
            return None

    def fetch_live_streams(self, channels):
        """Fetches live streams data from Twitch, and returns as list of
        dictionaries.
        """
        try:
            self.channels_count = len(channels)
            self.live_streams = []

            self.pages = int((self.channels_count - 1) / 75)
            for page in range(self.pages + 1):
                self.offset = (page * 75) + 75
                if (self.offset % 75 > 0):
                    self.offset = self.channels_count
                self.channels_offset = channels[(page * 75):self.offset]

                self.f = urlopen(
                    f'{TWITCH_API_URL}streams?client_id={CLIENT_ID}'
                    f'&channel={",".join(self.channels_offset)}')
                self.data = json.loads(self.f.read())

                for stream in self.data['streams']:
                    # For some reason sometimes stream status and game is not
                    # present in twitch API.
                    try:
                        self.status = stream['channel']['status']
                    except KeyError:
                        self.status = ''

                    # Show default if channel owner has not set his avatar
                    if stream['channel']['logo'] is None:
                        self.response = urlopen(DEFAULT_AVATAR)
                    else:
                        self.response = urlopen(stream['channel']['logo'])
                    self.loader = GdkPixbuf.PixbufLoader.new()
                    self.loader.set_size(32, 32)
                    self.loader.write(self.response.read())
                    self.loader.close()

                    st = {
                        'name': stream['channel']['display_name'],
                        'game': stream['channel']['game'],
                        'status': self.status,
                        'image': stream['channel']['logo'],
                        'pixbuf': self.loader,
                        'url': f"{TWITCH_BASE_URL}{stream['channel']['name']}"
                    }

                    self.live_streams.append(st)
            return self.live_streams
        except IOError:
            return None


class Indicator():
    SETTINGS_KEY = 'apps.twitch-indicator'
    LIVE_STREAMS = []

    def __init__(self):
        self.timeout_thread = None

        # Create applet
        self.a = appindicator.Indicator.new(
            'Twitch indicator',
            # TODO: hardcoded paths seem wrong
            '/usr/share/icons/twitch-indicator.svg',
            appindicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.a.set_status(appindicator.IndicatorStatus.ACTIVE)

        # Load settings
        self.settings = Gio.Settings.new(self.SETTINGS_KEY)

        # Setup menu
        self.menu = gtk.Menu()
        self.menuItems = [
            gtk.MenuItem(label='Check now'),
            gtk.SeparatorMenuItem(),
            gtk.MenuItem(label='Settings'),
            gtk.MenuItem(label='Quit')
        ]

        self.menuItems[0].connect(
            'activate', self.refresh_streams_init, [True])
        self.menuItems[-2].connect('activate', self.settings_dialog)
        self.menuItems[-1].connect('activate', self.quit)

        for i in self.menuItems:
            self.menu.append(i)

        self.a.set_menu(self.menu)

        self.menu.show_all()

        self.refresh_streams_init(None)

    def open_link(self, widget, url):
        """Opens link in a default browser."""
        webbrowser.open_new_tab(url)

    def refresh_streams_init(self, widget, button_activate=False):
        """Initializes thread for stream refreshing."""
        self.t = threading.Thread(target=self.refresh_streams)
        self.t.daemon = True
        self.t.start()

        if (button_activate is False):
            self.timeout_thread = threading.Timer(self.settings.get_int(
                'refresh-interval') * 60, self.refresh_streams_init, [None])
            self.timeout_thread.start()

    def settings_dialog(self, widget):
        """Shows applet settings dialog."""
        self.dialog = gtk.Dialog(
            'Settings',
            None,
            0,
            (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL,
             gtk.STOCK_OK, gtk.ResponseType.OK)
        )

        self.builder = gtk.Builder()
        # TODO: hardcoded paths seem wrong
        self.builder.add_from_file(
            '/usr/share/twitch-indicator/twitch-indicator.glade')

        self.builder.get_object('twitch_username').set_text(
            self.settings.get_string('twitch-username'))
        self.builder.get_object('show_notifications').set_active(
            self.settings.get_boolean('enable-notifications'))
        self.builder.get_object('refresh_interval').set_value(
            self.settings.get_int('refresh-interval'))

        self.box = self.dialog.get_content_area()
        self.box.add(self.builder.get_object('grid1'))
        self.response = self.dialog.run()

        if self.response == gtk.ResponseType.OK:
            self.settings.set_string(
                'twitch-username',
                self.builder.get_object('twitch_username').get_text())
            self.settings.set_boolean(
                'enable-notifications',
                self.builder.get_object('show_notifications').get_active())
            self.settings.set_int(
                'refresh-interval',
                self.builder.get_object('refresh_interval').get_value_as_int())
        elif self.response == gtk.ResponseType.CANCEL:
            pass

        self.dialog.destroy()

    def disable_menu(self):
        """Disables check now button."""
        self.menu.get_children()[0].set_sensitive(False)
        self.menu.get_children()[0].set_label('Checking...')

    def enable_menu(self):
        """Enables check now button."""
        self.menu.get_children()[0].set_sensitive(True)
        self.menu.get_children()[0].set_label('Check now')

    def add_streams_menu(self, streams):
        """Adds streams list to menu."""
        # Remove live streams menu if already exists
        if (len(self.menuItems) > 4):
            self.menuItems.pop(2)
            self.menuItems.pop(1)

        # Create menu
        self.streams_menu = gtk.Menu()
        self.menuItems.insert(2, gtk.MenuItem(
            label=f'Live channels ({len(streams)})'))
        self.menuItems.insert(3, gtk.SeparatorMenuItem())
        self.menuItems[2].set_submenu(self.streams_menu)

        # Order streams by alphabetical order
        self.streams_ordered = sorted(streams, key=lambda k: k['name'].lower())

        for index, stream in enumerate(self.streams_ordered):
            self.icon = gtk.Image()
            self.icon.set_from_pixbuf(stream['pixbuf'].get_pixbuf())
            self.menu_entry = gtk.ImageMenuItem(
                label=f"{stream['name']} - {stream['game']}")
            self.menu_entry.set_image(self.icon)
            self.streams_menu.append(self.menu_entry)
            self.streams_menu.get_children()[index].connect(
                'activate', self.open_link, stream['url'])

        for i in self.streams_menu.get_children():
            i.show()

        # Refresh all menu by removing and re-adding menu items
        for i in self.menu.get_children():
            self.menu.remove(i)

        for i in self.menuItems:
            self.menu.append(i)

        self.menu.show_all()

    def refresh_streams(self):
        """Refreshes live streams list. Also pushes notifications when needed.
        """
        GLib.idle_add(self.disable_menu)

        if (self.settings.get_string('twitch-username') == ''):
            GLib.idle_add(self.abort_refresh, 'Twitch.tv username is not set',
                          'Setup your username in settings')
            return

        # Create twitch instance and fetch followed channels.
        self.tw = Twitch()
        self.followed_channels = self.tw.fetch_followed_channels(
            self.settings.get_string('twitch-username'))

        # Does user exist?
        if self.followed_channels == 404:
            GLib.idle_add(
                self.abort_refresh,
                'Cannot retrieve followed channels from Twitch.tv',
                'User does not exist.')
            return

        if self.followed_channels is None:
            interval = self.settings.get_int('refresh-interval')
            GLib.idle_add(
                self.abort_refresh,
                'Cannot retrieve channel list from Twitch.tv',
                f'Retrying in {interval} minutes...')
            return

        self.live_streams = self.tw.fetch_live_streams(self.followed_channels)
        if self.live_streams is None:
            interval = self.settings.get_int('refresh-interval')
            GLib.idle_add(
                self.abort_refresh,
                'Cannot retrieve live streams from Twitch.tv',
                f'Retrying in {interval} minutes...')
            return

        # Update menu with live streams
        GLib.idle_add(self.add_streams_menu, self.live_streams)

        # Re-enable "Check now" button
        GLib.idle_add(self.enable_menu)

        # Check which streams were not live before, create separate list for
        # notifications and update main livestreams list.
        # We check live streams by URL, because sometimes Twitch API does not
        # show stream status, which makes notifications appear even if stream
        # has been live before.
        self.notify_list = list(self.live_streams)
        for x in self.LIVE_STREAMS:
            for y in self.live_streams:
                if x['url'] == y['url']:
                    self.notify_list[:] = [
                        d for d in self.notify_list if d.get('url') != y['url']
                    ]
                    break

        self.LIVE_STREAMS = self.live_streams

        # Push notifications of new streams
        if (self.settings.get_boolean('enable-notifications')):
            self.push_notifications(self.notify_list)

    def abort_refresh(self, message, description):
        """Updates menu with failure state message."""
        # Remove previous message if already exists
        if (len(self.menuItems) > 4):
            self.menuItems.pop(2)
            self.menuItems.pop(1)

        self.menuItems.insert(2, gtk.MenuItem(label=message))
        self.menuItems.insert(3, gtk.SeparatorMenuItem())
        self.menuItems[2].set_sensitive(False)

        # Re-enable "Check now" button
        self.menuItems[0].set_sensitive(True)
        self.menuItems[0].set_label('Check now')

        # Refresh all menu items
        for i in self.menu.get_children():
            self.menu.remove(i)

        for i in self.menuItems:
            self.menu.append(i)

        self.menu.show_all()

        # Push notification
        Notify.init('image')
        self.n = Notify.Notification.new(message, description, 'error').show()

    def push_notifications(self, streams):
        """Pushes notifications of every stream, passed as a list of
        dictionaries.
        """
        try:
            for stream in streams:
                self.image = gtk.Image()
                # Show default if channel owner has not set his avatar
                if stream['image'] is None:
                    self.response = urlopen(DEFAULT_AVATAR)
                else:
                    self.response = urlopen(stream['image'])
                self.loader = GdkPixbuf.PixbufLoader.new()
                self.loader.write(self.response.read())
                self.loader.close()

                Notify.init('image')
                self.n = Notify.Notification.new(
                    f"{stream['name']} just went LIVE!",
                    stream['status'],
                    '')

                self.n.set_icon_from_pixbuf(stream['pixbuf'].get_pixbuf())
                self.n.show()
        except IOError:
            return

    def main(self):
        """Main indicator function."""
        gtk.main()

    def quit(self, item):
        """Quits the applet."""
        self.timeout_thread.cancel()
        gtk.main_quit()


if __name__ == '__main__':
    gui = Indicator()
    gui.main()
