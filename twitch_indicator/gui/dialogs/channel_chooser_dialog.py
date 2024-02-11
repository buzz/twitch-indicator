import logging

from gi.repository import Gtk

from twitch_indicator.util import get_data_filepath


class ChannelChooserDialog:
    """Twitch indicator channel chooser dialog."""

    def __init__(self, gui_manager):
        self._logger = logging.getLogger(__name__)
        self._gui_manager = gui_manager
        self._reset_attributes()

    def _reset_attributes(self):
        self._dialog = None
        self._list_view = None
        self._search_text = ""
        self._label_followed = None
        self._label_enabled = None
        self._store = None
        self._filter = None

    def show(self, settings_dialog, skip_create=False):
        """Shows channel chooser dialog."""
        if self._dialog:
            self._dialog.present()
            return

        if skip_create:
            return

        self._dialog = Gtk.Dialog("Choose channels", settings_dialog, 0)
        self._dialog.set_border_width(10)
        self._dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        builder = Gtk.Builder()
        builder.add_from_file(
            get_data_filepath("twitch-indicator-channel-chooser.glade")
        )

        self._label_followed = builder.get_object("label_followed")
        self._label_enabled = builder.get_object("label_enabled")
        self._list_view = builder.get_object("list_view")

        # ListStore model
        self._store = Gtk.ListStore(str, bool, str)
        self._store.set_default_sort_func(self._sort_func)
        self._enable_sort()
        self._filter = self._store.filter_new()
        self._filter.set_visible_func(self._filter_func)

        self._add_model_data()

        self._list_view.get_selection().set_mode(Gtk.SelectionMode.NONE)
        self._list_view.set_model(self._filter)
        self._list_view.set_activate_on_single_click(True)

        renderer_name = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn("Streamer", renderer_name, text=0)
        col_name.set_expand(True)
        self._list_view.append_column(col_name)

        renderer_enabled = Gtk.CellRendererToggle()
        col_enabled = Gtk.TreeViewColumn("Enabled", renderer_enabled, active=1)
        col_enabled.set_expand(False)
        self._list_view.append_column(col_enabled)

        box = self._dialog.get_content_area()
        box.add(builder.get_object("content_box"))

        self._list_view.connect("row_activated", self._on_enabled_toggled)
        builder.get_object("entry_search").connect("changed", self._on_search_changed)
        builder.get_object("btn_enable_all").connect("clicked", self._on_enable_all)
        builder.get_object("btn_enable_none").connect("clicked", self._on_enable_none)
        builder.get_object("btn_invert").connect("clicked", self._on_invert)

        self._update_labels()

        if self._dialog.run() == Gtk.ResponseType.OK:
            self._commit_model_data()

        self.destroy()

    def destroy(self):
        """Destroy dialog window."""
        try:
            self._dialog.destroy()
        except AttributeError:
            pass
        self._reset_attributes()

    def _add_model_data(self):
        """Copy channel data to local model."""

        with self._gui_manager.app.state.locks["enabled_channel_ids"]:
            with self._gui_manager.app.state.locks["followed_channels"]:
                enabled_channel_ids = self._gui_manager.app.state.enabled_channel_ids
                for channel in self._gui_manager.app.state.followed_channels:
                    try:
                        val = enabled_channel_ids[channel["broadcaster_id"]]
                    except KeyError:
                        val = "0"

                    self._store.append(
                        [
                            channel["broadcaster_name"],
                            val == "1",
                            channel["broadcaster_id"],
                        ]
                    )

    def _commit_model_data(self):
        """Store channel data in app state."""
        enabled_channel_ids = {}
        for row in self._store:
            enabled_channel_ids[row[2]] = "1" if row[1] else "0"
        self._gui_manager.app.state.set_enabled_channel_ids(enabled_channel_ids)

    def _update_labels(self):
        """Update count labels."""
        enabled_count = sum(1 for c in self._store if c[1])
        self._label_followed.set_markup(f"Followed: <b>{len(self._store)}</b>")
        self._label_enabled.set_markup(f"Enabled: <b>{enabled_count}</b>")

    def _enable_sort(self, enabled=True):
        """Enable/disable sorting."""
        self._store.set_sort_column_id(
            (
                Gtk.TREE_SORTABLE_DEFAULT_SORT_COLUMN_ID
                if enabled
                else Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID
            ),
            Gtk.SortType.ASCENDING,
        )

    def _sort_func(self, model, row1, row2, _):
        """Sort entries by enabled, case-insensitive alphanumeric"""
        name1 = model.get_value(row1, 0).lower()
        enabled1 = model.get_value(row1, 1)
        name2 = model.get_value(row2, 0).lower()
        enabled2 = model.get_value(row2, 1)

        if enabled1 and not enabled2:
            return -1
        if not enabled1 and enabled2:
            return 1

        if name1 < name2:
            return -1
        if name1 == name2:
            return 0

        return 1

    def _filter_func(self, model, iter, _):
        """Filter list by search phrase."""
        if self._search_text == "":
            return True
        return self._search_text in model[iter][0].lower()

    def _on_enabled_toggled(self, tree_view, path, column):
        """Enabled checkbox toggled."""
        self._filter[path][1] = not self._filter[path][1]
        self._update_labels()

    def _on_search_changed(self, entry):
        """Update search phrase and refilter list."""
        self._search_text = entry.get_text().lower()
        self._filter.refilter()

    def _on_enable_all(self, _):
        """Enable all channels in current filter view."""
        self._enable_sort(False)
        for row in self._filter:
            row[1] = True
        self._enable_sort()
        self._update_labels()

    def _on_enable_none(self, _):
        """Disable all channels in current filter view."""
        self._enable_sort(False)
        for row in self._filter:
            row[1] = False
        self._enable_sort()
        self._update_labels()

    def _on_invert(self, _):
        """Invert enabled in current filter view."""
        self._enable_sort(False)
        for row in self._filter:
            row[1] = not row[1]
        self._enable_sort()
        self._update_labels()
