from gi.repository import Gtk

from twitch_indicator.util import get_data_filepath


class ChannelChooserDialog:
    """Twitch indicator channel chooser dialog."""

    def __init__(self, gui_manager):
        self._gui_manager = gui_manager
        self._dialog = None
        self._list_box = None
        self._entry_search = None
        self._enabled_channel_ids = {}
        self._restore_enabled()
        self._rows = {}
        self._checkboxes = {}

    def show(self, skip_create=False):
        """Shows channel chooser dialog."""
        if self._dialog:
            self._dialog.present()
            return

        if skip_create:
            return

        self._dialog = Gtk.Dialog("Channel chooser", None, 0)
        self._dialog.set_default_size(150, 500)

        builder = Gtk.Builder()
        builder.add_from_file(
            get_data_filepath("twitch-indicator-channel-chooser.glade")
        )

        self._dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self._dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)

        self._list_box = builder.get_object("list_box")
        self.add_channels()

        box = self._dialog.get_content_area()
        box.add(builder.get_object("content_box"))

        builder.get_object("btn_select_all").connect("clicked", self._on_select_all)
        builder.get_object("btn_select_none").connect("clicked", self._on_select_none)
        builder.get_object("btn_invert").connect("clicked", self._on_invert)
        builder.get_object("entry_search").connect("changed", self._on_search_changed)

        response = self._dialog.run()

        if response == Gtk.ResponseType.OK:
            self._store_enabled()

        try:
            self._dialog.destroy()
        except AttributeError:
            pass

        self._dialog = None
        self._entry_search = None
        self._list_box = None
        self._rows = {}
        self._checkboxes = {}

    def destroy(self):
        """Destroy dialog window."""
        try:
            self._dialog.destroy()
        except AttributeError:
            pass
        self._dialog = None
        self._list_box = None
        self._entry_search = None
        self._enabled_channel_ids = {}
        self._restore_enabled()
        self._rows = {}
        self._checkboxes = {}

    def add_channels(self):
        """Add followed channel to list."""
        followed_channels = self._gui_manager.app.followed_channels
        channels_sorted = sorted(
            followed_channels, key=lambda ch: ch["broadcaster_login"].lower()
        )
        for channel in channels_sorted:
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

            check_button = Gtk.CheckButton()
            if channel["broadcaster_id"] not in self._enabled_channel_ids:
                self._enabled_channel_ids[channel["broadcaster_id"]] = True
            val = self._enabled_channel_ids[channel["broadcaster_id"]]
            check_button.set_active(val)
            check_button.connect("toggled", self._on_toggled, channel["broadcaster_id"])
            hbox.pack_start(check_button, False, False, 8)

            label = Gtk.Label(label=channel["broadcaster_name"])
            label.halign = Gtk.Align.START
            hbox.pack_start(label, False, False, 8)

            row = Gtk.ListBoxRow()
            row.add(hbox)
            self._list_box.add(row)

            self._rows[channel["broadcaster_name"]] = row
            self._checkboxes[channel["broadcaster_id"]] = check_button

        self._list_box.show_all()

    @property
    def enabled_channel_ids(self):
        return self._enabled_channel_ids

    def _restore_enabled(self):
        """Get and parse enabled channel IDs from settings."""
        settings = self._gui_manager.app.settings
        enabled_str = settings.get_string("enabled-channel-ids")
        try:
            for channel in enabled_str.split(","):
                channel_id, onoff = channel.split(":")
                channel_id = int(channel_id)
                if onoff == "1":
                    self._enabled_channel_ids[channel_id] = True
                else:
                    self._enabled_channel_ids[channel_id] = False
        except Exception:
            pass

    def _store_enabled(self):
        """Store enabled channel IDs from settings."""
        enabled_list = []
        settings = self._gui_manager.app.settings

        for channel_id, enabled in self._enabled_channel_ids.items():
            onoff = "1" if enabled else "0"
            enabled_list.append(f"{channel_id}:{onoff}")

        enabled_str = ",".join(enabled_list)
        settings.set_string("enabled-channel-ids", enabled_str)

    def _on_toggled(self, checkbox, channel_id):
        """Toggle a channel."""
        if checkbox.get_active():
            self._enabled_channel_ids[channel_id] = True
        else:
            self._enabled_channel_ids[channel_id] = False

    def _on_search_changed(self, entry):
        """Search list."""
        search_text = entry.get_text().lower()
        for name, row in self._rows.items():
            row.set_visible(search_text in name.lower())

    def _on_select_all(self, _):
        """Select all channel."""
        for channel_id, checkbox in self._checkboxes.items():
            self._enabled_channel_ids[channel_id] = True
            checkbox.set_active(True)

    def _on_select_none(self, _):
        """Deselect all channel."""
        for channel_id, checkbox in self._checkboxes.items():
            self._enabled_channel_ids[channel_id] = False
            checkbox.set_active(False)

    def _on_invert(self, _):
        """Invert selection."""
        for channel_id, checkbox in self._checkboxes.items():
            new_val = not self._enabled_channel_ids[channel_id]
            self._enabled_channel_ids[channel_id] = new_val
            checkbox.set_active(new_val)
