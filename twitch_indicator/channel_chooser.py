from gi.repository import Gtk

from twitch_indicator.util import get_data_filepath


class ChannelChooser:
    """Twitch indicator channel chooser dialog."""

    def __init__(self, app):
        self.app = app
        self.dialog = None
        self.list_box = None
        self.entry_search = None
        self.enabled_channel_ids = {}
        self.restore_enabled()
        self.rows = {}
        self.checkboxes = {}

    def show(self):
        """Shows channel chooser dialog."""

        self.dialog = Gtk.Dialog("Channel chooser", None, 0)
        self.dialog.set_default_size(150, 500)

        builder = Gtk.Builder()
        builder.add_from_file(
            get_data_filepath("twitch-indicator-channel-chooser.glade")
        )

        self.dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)

        self.list_box = builder.get_object("list_box")
        self.add_channels()

        box = self.dialog.get_content_area()
        box.add(builder.get_object("content_box"))

        builder.get_object("btn_select_all").connect("clicked", self.on_select_all)
        builder.get_object("btn_select_none").connect("clicked", self.on_select_none)
        builder.get_object("btn_invert").connect("clicked", self.on_invert)
        builder.get_object("entry_search").connect("changed", self.on_search_changed)

        response = self.dialog.run()

        if response == Gtk.ResponseType.OK:
            self.store_enabled()

        self.dialog.destroy()
        self.dialog = None
        self.entry_search = None
        self.list_box = None
        self.rows = {}
        self.checkboxes = {}

    def add_channels(self):
        """Add followed channel to list."""
        channels_sorted = sorted(
            self.app.followed_channels, key=lambda ch: ch["name"].lower()
        )
        for channel in channels_sorted:
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

            check_button = Gtk.CheckButton()
            if not channel["id"] in self.enabled_channel_ids:
                self.enabled_channel_ids[channel["id"]] = True
            check_button.set_active(self.enabled_channel_ids[channel["id"]])
            check_button.connect("toggled", self.on_toggled, channel["id"])
            hbox.pack_start(check_button, False, False, 8)

            label = Gtk.Label(label=channel["name"])
            label.halign = Gtk.Align.START
            hbox.pack_start(label, False, False, 8)

            row = Gtk.ListBoxRow()
            row.add(hbox)
            self.list_box.add(row)

            self.rows[channel["name"]] = row
            self.checkboxes[channel["id"]] = check_button

        self.list_box.show_all()

    def restore_enabled(self):
        """Get and parse enabled channel IDs from settings."""
        enabled_str = self.app.settings.settings.get_string("enabled-channel-ids")
        try:
            for channel in enabled_str.split(","):
                channel_id, onoff = channel.split(":")
                channel_id = int(channel_id)
                if onoff == "1":
                    self.enabled_channel_ids[channel_id] = True
                else:
                    self.enabled_channel_ids[channel_id] = False
        except:  # pylint: disable=bare-except
            pass

    def store_enabled(self):
        """Store enabled channel IDs from settings."""
        enabled_list = []

        for channel_id, enabled in self.enabled_channel_ids.items():
            onoff = "1" if enabled else "0"
            enabled_list.append(f"{channel_id}:{onoff}")

        enabled_str = ",".join(enabled_list)
        self.app.settings.settings.set_string("enabled-channel-ids", enabled_str)

    def on_toggled(self, checkbox, channel_id):
        """Toggle a channel."""
        if checkbox.get_active():
            self.enabled_channel_ids[channel_id] = True
        else:
            self.enabled_channel_ids[channel_id] = False

    def on_search_changed(self, entry):
        """Search list."""
        search_text = entry.get_text().lower()
        for name, row in self.rows.items():
            row.set_visible(search_text in name.lower())

    def on_select_all(self, _):
        """Select all channel."""
        for channel_id, checkbox in self.checkboxes.items():
            self.enabled_channel_ids[channel_id] = True
            checkbox.set_active(True)

    def on_select_none(self, _):
        """Deselect all channel."""
        for channel_id, checkbox in self.checkboxes.items():
            self.enabled_channel_ids[channel_id] = False
            checkbox.set_active(False)

    def on_invert(self, _):
        """Invert selection."""
        for channel_id, checkbox in self.checkboxes.items():
            new_val = not self.enabled_channel_ids[channel_id]
            self.enabled_channel_ids[channel_id] = new_val
            checkbox.set_active(new_val)
