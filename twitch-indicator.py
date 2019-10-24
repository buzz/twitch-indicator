#!/usr/bin/env python3

import threading
import webbrowser
import json
from urllib.request import urlopen, Request, HTTPError
import gi

from pprint import pprint

gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
gi.require_version('Gtk', '3.0')
from gi.repository import AppIndicator3 as appindicator  # noqa: E402
from gi.repository import GLib, Gio, Notify, GdkPixbuf  # noqa: E402
from gi.repository import Gtk as gtk  # noqa: E402

TWITCH_BASE_URL = 'https://www.twitch.tv/'
TWITCH_API_URL = 'https://api.twitch.tv/helix/'
DEFAULT_AVATAR = 'http://static-cdn.jtvnw.net/jtv_user_pictures/xarth/404_user_150x150.png'
CLIENT_ID = 'oe77z9pq798tln7ngil0exwr0mun4hj'


class Twitch:
    CHANNEL_INFO_CACHE = {}
    GAME_INFO_CACHE = {}

    def clear_cache(self):
        self.CHANNEL_INFO_CACHE.clear()
        self.GAME_INFO_CACHE.clear()

    def fetch_followed_channels(self, user_id):
        """Fetch user followed channels and return a list with channel ids."""
        base_uri = TWITCH_API_URL + 'users/follows?from_id=' + user_id
        resp = self.get_api_decoded_response(base_uri)
        if type(resp) == HTTPError:
            return resp

        total = int(resp['total'])
        fetched = len(resp['data'])
        data = resp['data']

        # User has not followed any channels
        if total == 0:
            return None

        last = resp
        while fetched < total:
            nxt = self.get_api_decoded_response(base_uri + '&after=' + last['pagination']['cursor'])
            if type(nxt) == HTTPError:
                return nxt

            fetched += len(nxt['data'])
            data += nxt['data']
            last = nxt

        return [data['to_id'] for data in data]

    def fetch_live_streams(self, channel_ids):
        """Fetches live streams data from Twitch, and returns as list of
        dictionaries.
        """
        api_channel_limit = 100
        base_uri = TWITCH_API_URL + 'streams'

        channel_index = 0
        channel_max = api_channel_limit

        channels_live = []

        while channel_index < len(channel_ids):
            curr_channels = channel_ids[channel_index:channel_max]
            channel_index += len(curr_channels)
            channel_max += api_channel_limit

            suffix = '?user_id=' + '&user_id='.join(curr_channels)
            resp = self.get_api_decoded_response(base_uri + suffix)

            [channels_live.append(c) for c in resp['data']]

        streams = []
        for stream in channels_live:
            channel_info = self.get_channel_info(stream['user_id'])
            game_info = self.get_game_info(stream['game_id'])

            channel_image = urlopen(
                channel_info['profile_image_url']
                if channel_info['profile_image_url']
                else DEFAULT_AVATAR
            )
            image_loader = GdkPixbuf.PixbufLoader.new()
            image_loader.set_size(128, 128)
            image_loader.write(channel_image.read())
            image_loader.close()

            st = {
                'name': channel_info['display_name'],
                'game': game_info['name'],
                'title': stream['title'],
                'image': channel_info['profile_image_url'],
                'pixbuf': image_loader,
                'url': f"{TWITCH_BASE_URL}{channel_info['login']}"
            }
            streams.append(st)

        return streams

    def get_channel_info(self, channel_id):
        channel_info = self.CHANNEL_INFO_CACHE.get(int(channel_id))
        if channel_info is not None:
            return channel_info

        resp = self.get_api_decoded_response(TWITCH_API_URL + 'users?id=' + channel_id)
        if type(resp) == HTTPError:
            return resp
        elif not len(resp['data']) == 1:
            return None

        self.CHANNEL_INFO_CACHE[int(channel_id)] = resp['data'][0]
        return resp['data'][0]

    def get_game_info(self, game_id):
        game_info = self.GAME_INFO_CACHE.get(int(game_id))
        if game_info is not None:
            return game_info

        resp = self.get_api_decoded_response(TWITCH_API_URL + 'games?id=' + game_id)
        if type(resp) == HTTPError:
            return resp
        elif not len(resp['data']) == 1:
            return None

        self.GAME_INFO_CACHE[int(game_id)] = resp['data'][0]
        return resp['data'][0]

    def get_user_id(self, username):
        resp = self.get_api_decoded_response(TWITCH_API_URL + 'users?login=' + username)
        if type(resp) == HTTPError:
            return resp
        elif not len(resp['data']) == 1:
            return None
        return resp['data'][0]['id']

    def get_api_decoded_response(self, url):
        headers = {'Client-ID': CLIENT_ID}
        req = Request(url, headers=headers)
        try:
            resp = urlopen(req).read()
            decoded = json.loads(resp)
            return decoded
        except HTTPError as e:
            return e


class Indicator:
    SETTINGS_KEY = 'apps.twitch-indicator'
    LIVE_STREAMS = []
    USER_ID = None

    def __init__(self):
        self.t = None
        self.timeout_thread = None
        self.tw = None

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

    def clear_cache(self):
        self.USER_ID = None
        self.tw.clear_cache()

    def open_link(self, widget, url):
        """Opens link in a default browser."""
        webbrowser.open_new_tab(url)

    def refresh_streams_init(self, widget, button_activate=False):
        self.tw = Twitch()

        """Initializes thread for stream refreshing."""
        self.t = threading.Thread(target=self.refresh_streams)
        self.t.daemon = True
        self.t.start()

        if button_activate is False:
            self.timeout_thread = threading.Timer(self.settings.get_int(
                'refresh-interval') * 60, self.refresh_streams_init, [None])
            self.timeout_thread.start()

    def settings_dialog(self, widget):
        """Shows applet settings dialog."""
        dialog = gtk.Dialog('Settings', None, 0)
        dialog.add_buttons(
            gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL,
            gtk.STOCK_OK, gtk.ResponseType.OK
        )

        builder = gtk.Builder()
        # TODO: hardcoded paths seem wrong
        builder.add_from_file(
            '/usr/share/twitch-indicator/twitch-indicator.glade')

        builder.get_object('twitch_username').set_text(
            self.settings.get_string('twitch-username'))
        builder.get_object('show_notifications').set_active(
            self.settings.get_boolean('enable-notifications'))
        builder.get_object('refresh_interval').set_value(
            self.settings.get_int('refresh-interval'))

        box = dialog.get_content_area()
        box.add(builder.get_object('grid1'))
        response = dialog.run()

        if response == gtk.ResponseType.OK:
            self.settings.set_string(
                'twitch-username',
                builder.get_object('twitch_username').get_text())
            self.settings.set_boolean(
                'enable-notifications',
                builder.get_object('show_notifications').get_active())
            self.settings.set_int(
                'refresh-interval',
                builder.get_object('refresh_interval').get_value_as_int())

            self.clear_cache()
        elif response == gtk.ResponseType.CANCEL:
            pass

        dialog.destroy()

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
        if len(self.menuItems) > 4:
            self.menuItems.pop(2)
            self.menuItems.pop(1)

        # Create menu
        streams_menu = gtk.Menu()
        self.menuItems.insert(2, gtk.MenuItem(
            label=f'Live channels ({len(streams)})'))
        self.menuItems.insert(3, gtk.SeparatorMenuItem())
        self.menuItems[2].set_submenu(streams_menu)

        # Order streams by alphabetical order
        streams_ordered = sorted(streams, key=lambda k: k['name'].lower())

        for index, stream in enumerate(streams_ordered):
            menu_entry = gtk.MenuItem(
                label=f"{stream['name']} - {stream['game']}")
            streams_menu.append(menu_entry)
            streams_menu.get_children()[index].connect(
                'activate', self.open_link, stream['url'])

        for i in streams_menu.get_children():
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

        if self.settings.get_string('twitch-username') == '':
            GLib.idle_add(self.abort_refresh, None, 'Twitch.tv username is not set',
                          'Setup your username in settings')
            return

        if self.USER_ID is None:
            self.USER_ID = self.tw.get_user_id(self.settings.get_string('twitch-username'))
            if self.USER_ID is None:
                GLib.idle_add(self.abort_refresh, None, 'Cannot resolve Twitch.tv username',
                              'Setup your username in settings')
                return

        # fetch followed channels
        followed_channels = self.tw.fetch_followed_channels(self.USER_ID)

        # Did an error occur?
        if type(followed_channels) == HTTPError:
            interval = self.settings.get_int('refresh-interval')
            GLib.idle_add(
                self.abort_refresh, followed_channels,
                'Cannot retrieve channel list from Twitch.tv',
                f'Retrying in {interval} minutes...')
            return

        # Are there channels that the user follows?
        elif followed_channels is None:
            return

        # Fetch live streams
        live_streams = self.tw.fetch_live_streams(followed_channels)

        # Did an error occur?
        if type(live_streams) == HTTPError:
            interval = self.settings.get_int('refresh-interval')
            GLib.idle_add(
                self.abort_refresh, live_streams,
                'Cannot retrieve live streams from Twitch.tv',
                f'Retrying in {interval} minutes...')
            return

        # Are there *live* streams?
        elif live_streams is None:
            return

        # Update menu with live streams
        GLib.idle_add(self.add_streams_menu, live_streams)

        # Re-enable "Check now" button
        GLib.idle_add(self.enable_menu)

        # Check which streams were not live before, create separate list for
        # notifications and update main livestreams list.
        # We check live streams by URL, because sometimes Twitch API does not
        # show stream status, which makes notifications appear even if stream
        # has been live before.
        notify_list = list(live_streams)
        for x in self.LIVE_STREAMS:
            for y in live_streams:
                if x['url'] == y['url']:
                    notify_list[:] = [
                        d for d in notify_list if d.get('url') != y['url']
                    ]
                    break

        self.LIVE_STREAMS = live_streams

        # Push notifications of new streams
        if self.settings.get_boolean('enable-notifications'):
            self.push_notifications(notify_list)

    def abort_refresh(self, exception, message, description):
        """Updates menu with failure state message."""
        # Remove previous message if already exists
        if len(self.menuItems) > 4:
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
        Notify.init('Twitch Indicator')

        if type(exception) == HTTPError:
            message = str(exception.code) + ': ' + message
        Notify.Notification.new(message, description, 'error').show()

    def push_notifications(self, streams):
        """Pushes notifications of every stream, passed as a list of
        dictionaries.
        """

        for stream in streams:
            image = gtk.Image()
            # Show default if channel owner has not set his avatar

            Notify.init('Twitch Notification')
            n = Notify.Notification.new(
                f"{stream['name']} just went LIVE!",
                stream['title'],
                '')

            # Fixed deprecation warning
            n.set_image_from_pixbuf(stream['pixbuf'].get_pixbuf())
            n.show()

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
