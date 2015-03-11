#!/usr/bin/python

import appindicator
import pynotify
import urllib
import json
import sys
import os
import webbrowser

import gobject
import gtk
gtk.gdk.threads_init()

import threading

class Twitch:
  def fetch_followed_channels(self, username):
    """Fetch user followed channels and return a list with channel names."""
    try:
      self.followed_channels = []
      
      self.f = urllib.urlopen("https://api.twitch.tv/kraken/users/{0}/follows/channels?direction=DESC&limit=100&offset=0&sortby=created_at".format(username))
      self.data = json.loads(self.f.read())

      self.pages = (self.data['_total'] - 1) / 100
      for page in range(0, self.pages + 1):
        if page != 0:
          self.f = urllib.urlopen("https://api.twitch.tv/kraken/users/{0}/follows/channels?direction=DESC&limit=100&offset={1}&sortby=created_at".format(username, (page * 100)))
          self.data = json.loads(self.f.read())

        for channel in self.data['follows']:
          self.followed_channels.append(channel['channel']['display_name'])
      
      return self.followed_channels
    except IOError:
      return None

  def fetch_live_streams(self, channels):
    """Fetches live streams data from Twitch, and returns as list of dictionaries"""
    try:
      self.channels_count = len(channels)
      self.live_streams = []
      
      self.pages = (self.channels_count - 1) / 75
      for page in range(0, self.pages + 1):
        self.offset = (page * 75) + 75
        if (self.offset % 75 > 0):
          self.offset = self.channels_count 
        self.channels_offset = channels[(page * 75):self.offset]

        self.f = urllib.urlopen("https://api.twitch.tv/kraken/streams?channel={0}".format(','.join(self.channels_offset)))
        self.data = json.loads(self.f.read())

        for stream in self.data['streams']:
          # For some reason sometimes stream status and game is not present in
          # twitch API.
          try:
            self.status = stream['channel']['status']
          except KeyError:
            self.status = ""
          
          st = {
            'name': stream['channel']['display_name'],
            'status': self.status,
            'image': stream['channel']['logo'],
            'url': "http://www.twitch.tv/%s" % stream['channel']['name']
          }

          self.live_streams.append(st)
      return self.live_streams
    except IOError:
      return None

class Indicator():
  def __init__(self):
    # Setup applet icon depending on DE
    self.desktop_env = os.environ.get('DESKTOP_SESSION')
    if self.desktop_env == "pantheon":
      self.applet_icon = "indicator_elementary.png"
    else:
      self.applet_icon = "indicator_ubuntu.png"

    # Create applet
    self.a = appindicator.Indicator(
      'wallch_indicator',
      os.path.dirname(os.path.abspath(__file__)) + "/icons/%s" % self.applet_icon,
      appindicator.CATEGORY_APPLICATION_STATUS
    )
    self.a.set_status(appindicator.STATUS_ACTIVE)

    # Setup menu
    self.menu = gtk.Menu()
    self.menuItems = [
      gtk.MenuItem('Check now'),
      gtk.SeparatorMenuItem(),
      gtk.MenuItem('Settings'),
      gtk.MenuItem('Quit')
    ]

    for i in self.menuItems:
      self.menu.append(i)

    self.a.set_menu(self.menu)

    for i in self.menu.get_children():
      i.show()

    self.menuItems[0].connect('activate', self.refresh_streams_init)
    self.menuItems[-2].connect('activate', self.settings_dialog)
    self.menuItems[-1].connect('activate', self.quit)
    
    # Runtime variables
    self.currentLiveStreams = []

  def rebuild_menu(self):
    self.menuItems = [
      gtk.MenuItem('Check now'),
      gtk.SeparatorMenuItem(),
      gtk.MenuItem('Settings'),
      gtk.MenuItem('Quit')
    ]

    self.menuItems[0].connect('activate', self.refresh_streams_init)
    self.menuItems[-2].connect('activate', self.settings_dialog)
    self.menuItems[-1].connect('activate', self.quit)

  def refresh_menu(self):
    """Rebuilds indicator menu."""
    for i in self.menu.get_children():
      self.menu.remove(i)

    for i in self.menuItems:
      self.menu.append(i)

    for i in self.menu.get_children():
      i.show()

  def open_link(self, widget, url):
    """Opens link in a default browser."""
    webbrowser.open_new_tab(url)

  def refresh_streams_init(self, widget):
    """Initializes thread for stream refreshing."""
    threading.Thread(target=self.refresh_streams, args=(widget)).start()

  def settings_dialog(self, widget):
    """Shows applet settings dialog."""
    self.dialog = gtk.Dialog(
      "Settings",
      None,
      gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
      (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
       gtk.STOCK_OK, gtk.RESPONSE_ACCEPT)
    )

    self.table = gtk.Table(2, 2, False)

    self.username_label = gtk.Label("Twitch username")
    self.username_input = gtk.Entry()

    self.notifications_label = gtk.Label("Enable notifications")
    self.notifications_checkbox = gtk.CheckButton()

    self.table.attach(self.username_label, 0, 1, 0, 1, gtk.FILL, gtk.FILL, 6, 2)
    self.table.attach(self.username_input, 1, 2, 0, 1, gtk.FILL, gtk.FILL, 6, 2)
    self.table.attach(self.notifications_label, 0, 1, 1, 2, gtk.FILL, gtk.FILL, 6, 2)
    self.table.attach(self.notifications_checkbox, 1, 2, 1, 2, gtk.FILL, gtk.FILL, 6, 2)

    self.dialog.vbox.pack_start(self.table)

    self.username_label.show()
    self.username_input.show()
    self.notifications_label.show()
    self.notifications_checkbox.show()
    self.table.show()

    self.dialog.run()
    self.dialog.destroy()

  def refresh_streams(self, items):
    """Refreshes live streams list. Also pushes notifications when needed."""
    self.rebuild_menu()
    self.refresh_menu()

    # Disable check now button in menu and update text.
    self.menuItems[0].set_sensitive(False)
    self.menuItems[0].set_label("Checking...")
    self.refresh_menu()

    # Create twitch instance and fetch followed channels.
    self.tw = Twitch()
    self.followed_channels = self.tw.fetch_followed_channels("xrbrs")

    # If we can't retrieve channels, update menu accordingly.
    if self.followed_channels == None:
      self.menuItems.insert(2, gtk.MenuItem("Cannot retrieve channels"))
      self.menuItems.insert(3, gtk.SeparatorMenuItem())
      self.menuItems[2].set_sensitive(False)

      # Re-enable "Check now" button
      self.menuItems[0].set_sensitive(True)
      self.menuItems[0].set_label("Check now")
      self.refresh_menu()

      # Stop further execution.
      return

    # Fetch live streams
    self.live_streams = self.tw.fetch_live_streams(self.followed_channels)

    # If we can't retrieve streams, update menu accordingly.
    if self.live_streams == None:
      self.menuItems.insert(2, gtk.MenuItem("Cannot retrieve live streams"))
      self.menuItems.insert(3, gtk.SeparatorMenuItem())
      self.menuItems[2].set_sensitive(False)

      # Re-enable "Check now" button
      self.menuItems[0].set_sensitive(True)
      self.menuItems[0].set_label("Check now")
      self.refresh_menu()

      # Stop further execution.
      return

    # Update menu with live streams
    self.streams_menu = gtk.Menu() 
    self.menuItems.insert(2, gtk.MenuItem("Live channels ({0})".format(len(self.live_streams))))
    self.menuItems.insert(3, gtk.SeparatorMenuItem())
    self.menuItems[2].set_submenu(self.streams_menu)

    for index, stream in enumerate(self.live_streams):
      self.streams_menu.append(gtk.MenuItem(stream["name"]))
      self.streams_menu.get_children()[index].connect('activate', self.open_link, stream["url"])
    
    for i in self.streams_menu.get_children():
      i.show()
    
    # Push notifications of new streams
    self.push_notifications(self.live_streams)

    # Re-enable "Check now" button
    self.menuItems[0].set_sensitive(True)
    self.menuItems[0].set_label("Check now")
    self.refresh_menu()

  def push_notifications(self, streams):
    """Pushes notifications of every stream, passed as a list of dictionaries."""
    try:
      for stream in streams:
        self.image = gtk.Image()
        self.response = urllib.urlopen(stream["image"])
        self.loader = gtk.gdk.PixbufLoader()
        self.loader.write(self.response.read())
        self.loader.close()

        pynotify.init("image")
        self.n = pynotify.Notification("%s just went LIVE!" % stream["name"],
          stream["status"],
          "",
        )

        self.n.set_icon_from_pixbuf(self.loader.get_pixbuf())
        
        self.n.show()
    except IOError:
      return None

  def main(self):
    """Main indicator function."""
    gtk.main()

  def quit(self, item):
    """Quits the applet."""
    gtk.main_quit()

if __name__=="__main__":
  gui = Indicator()
  gtk.gdk.threads_enter()
  gui.main()
  gtk.gdk.threads_leave()