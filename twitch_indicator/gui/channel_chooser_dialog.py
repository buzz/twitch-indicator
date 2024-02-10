import copy
import logging

from gi.repository import Gtk

from twitch_indicator.util import get_data_filepath


class ChannelChooserDialog:
    """Twitch indicator channel chooser dialog."""

    def __init__(self, gui_manager):
        self._logger = logging.getLogger(__name__)
        self._gui_manager = gui_manager
        self._dialog = None
        self._list_box = None
        self._entry_search = None
        self._enabled_channel_ids = None
        self._rows = {}
        self._checkboxes = {}
        self._label_followed = None
        self._label_enabled = None

    def show(self, skip_create=False):
        """Shows channel chooser dialog."""
        if self._dialog:
            self._dialog.present()
            return

        if skip_create:
            return

        with self._gui_manager.app.state.locks["enabled_channel_ids"]:
            state = self._gui_manager.app.state
            self._enabled_channel_ids = copy.deepcopy(state.enabled_channel_ids)

        self._dialog = Gtk.Dialog("Channel chooser", None, 0)
        self._dialog.set_default_size(150, 500)
        self._dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        builder = Gtk.Builder()
        builder.add_from_file(
            get_data_filepath("twitch-indicator-channel-chooser.glade")
        )

        self._list_box = builder.get_object("list_box")
        self._label_followed = builder.get_object("label_followed")
        self._label_enabled = builder.get_object("label_enabled")

        self.add_channels()

        box = self._dialog.get_content_area()
        box.add(builder.get_object("content_box"))

        builder.get_object("btn_select_all").connect("clicked", self._on_select_all)
        builder.get_object("btn_select_none").connect("clicked", self._on_select_none)
        builder.get_object("btn_invert").connect("clicked", self._on_invert)
        builder.get_object("entry_search").connect("changed", self._on_search_changed)

        response = self._dialog.run()

        if response == Gtk.ResponseType.OK:
            self._gui_manager.app.state.set_enabled_channel_ids(
                self._enabled_channel_ids
            )

        self.destroy()

    def destroy(self):
        """Destroy dialog window."""
        try:
            self._dialog.destroy()
        except AttributeError:
            pass
        self._dialog = None
        self._list_box = None
        self._entry_search = None
        self._enabled_channel_ids = None
        self._rows = {}
        self._checkboxes = {}
        self._label_followed = None
        self._label_enabled = None

    def add_channels(self):
        """Add followed channel to list."""

        with self._gui_manager.app.state.locks["followed_channels"]:
            followed_channels = self._gui_manager.app.state.followed_channels
            channels_sorted = sorted(
                followed_channels, key=lambda ch: ch["broadcaster_login"].lower()
            )

        self._label_followed.set_text(f"Followed: {len(followed_channels)}")
        self._update_label_enabled()

        for channel in channels_sorted:
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

            check_button = Gtk.CheckButton()
            try:
                val = self._enabled_channel_ids[channel["broadcaster_id"]]
            except KeyError:
                val = self._enabled_channel_ids[channel["broadcaster_id"]] = True

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

    def _update_label_enabled(self):
        enabled_count = len(
            [onoff for onoff in self._enabled_channel_ids.values() if onoff]
        )
        self._label_enabled.set_text(f"Enabled: {enabled_count}")

    def _on_toggled(self, checkbox, channel_id):
        """Toggle a channel."""
        self._enabled_channel_ids[channel_id] = checkbox.get_active()
        self._update_label_enabled()

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
        self._update_label_enabled()

    def _on_select_none(self, _):
        """Deselect all channel."""
        for channel_id, checkbox in self._checkboxes.items():
            self._enabled_channel_ids[channel_id] = False
            checkbox.set_active(False)
        self._update_label_enabled()

    def _on_invert(self, _):
        """Invert selection."""
        for channel_id, checkbox in self._checkboxes.items():
            new_val = not self._enabled_channel_ids[channel_id]
            self._enabled_channel_ids[channel_id] = new_val
            checkbox.set_active(new_val)
        self._update_label_enabled()
