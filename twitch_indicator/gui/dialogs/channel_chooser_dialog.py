import asyncio
import logging

from gi.repository import Gtk

from twitch_indicator.constants import TWITCH_MAX_SUBSCRIPTIONS
from twitch_indicator.util import coro_exception_handler, get_data_filepath


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
        self._label_realtime = None
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
        self._label_realtime = builder.get_object("label_realtime")
        self._list_view = builder.get_object("list_view")

        # ListStore model (name, real-time, enabled)
        self._store = Gtk.ListStore(str, bool, bool, str)
        self._store.set_default_sort_func(self._sort_func)
        self._enable_sort()
        self._filter = self._store.filter_new()
        self._filter.set_visible_func(self._filter_func)

        self._add_model_data()

        self._list_view.get_selection().set_mode(Gtk.SelectionMode.NONE)
        self._list_view.set_model(self._filter)
        renderer_name = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn("Streamer", renderer_name, text=0)
        col_name.set_expand(True)
        self._list_view.append_column(col_name)

        renderer_realtime = Gtk.CellRendererToggle()
        renderer_realtime.connect("toggled", self._on_realtime_toggled)
        col_realtime = Gtk.TreeViewColumn("Real-time", renderer_realtime, active=1)
        col_realtime.set_expand(False)
        self._list_view.append_column(col_realtime)

        renderer_enabled = Gtk.CellRendererToggle()
        renderer_enabled.connect("toggled", self._on_enabled_toggled)
        col_enabled = Gtk.TreeViewColumn("Enabled", renderer_enabled, active=2)
        col_enabled.set_expand(False)
        self._list_view.append_column(col_enabled)

        box = self._dialog.get_content_area()
        box.add(builder.get_object("content_box"))

        builder.get_object("entry_search").connect("changed", self._on_search_changed)
        builder.get_object("btn_enable_all").connect("clicked", self._on_enable_all)
        builder.get_object("btn_enable_none").connect("clicked", self._on_enable_none)
        builder.get_object("btn_invert").connect("clicked", self._on_invert)
        builder.get_object("btn_refresh").connect("clicked", self._on_refresh)

        self._update_labels()

        if self._dialog.run() == Gtk.ResponseType.OK:
            self._save_model_data()

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
                        mode = enabled_channel_ids[channel["broadcaster_id"]]
                    except KeyError:
                        mode = "0"

                    self._store.append(
                        [
                            channel["broadcaster_name"],
                            mode == "2",
                            mode != "0",
                            channel["broadcaster_id"],
                        ]
                    )

    def _save_model_data(self):
        """Store channel data in state."""
        enabled_channel_ids = {}
        for row in self._store:
            if row[1]:  # realtime
                enabled_channel_ids[row[3]] = "2"
            elif row[2]:  # enabled
                enabled_channel_ids[row[3]] = "1"

        self._gui_manager.app.state.set_enabled_channel_ids(enabled_channel_ids)

    def _update_labels(self):
        """Update count labels."""
        self._label_followed.set_markup(f"<b>Followed:</b> {len(self._store)}")
        self._label_realtime.set_markup(
            f"<b>Real-time:</b> {self._realtime_count} of {TWITCH_MAX_SUBSCRIPTIONS}"
        )
        self._label_enabled.set_markup(f"<b>Enabled:</b> {self._enabled_count}")

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
        realtime1 = model.get_value(row1, 1)
        enabled1 = model.get_value(row1, 2)
        name2 = model.get_value(row2, 0).lower()
        realtime2 = model.get_value(row2, 1)
        enabled2 = model.get_value(row2, 2)

        if realtime1 and not realtime2:
            return -1
        if not realtime1 and realtime2:
            return 1

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

    @property
    def _enabled_count(self):
        return sum(1 for c in self._store if c[2])

    @property
    def _realtime_count(self):
        return sum(1 for c in self._store if c[1])

    def _on_realtime_toggled(self, cell_renderer, path):
        """Real-time checkbox toggled."""
        max_used = self._realtime_count >= TWITCH_MAX_SUBSCRIPTIONS

        self._enable_sort(False)
        if self._filter[path][1]:
            self._filter[path][1] = False
        elif not max_used:
            self._filter[path][1] = True
            self._filter[path][2] = True
        self._enable_sort()
        self._update_labels()

    def _on_enabled_toggled(self, cell_renderer, path):
        """Enabled checkbox toggled."""
        self._enable_sort(False)
        if self._filter[path][2]:
            self._filter[path][1] = False
            self._filter[path][2] = False
        else:
            self._filter[path][2] = True
        self._enable_sort()
        self._update_labels()

    def _on_search_changed(self, entry):
        """Update search phrase and refilter list."""
        self._search_text = entry.get_text().lower()
        self._filter.refilter()

    def _on_enable_all(self, _):
        """Enable all channels in current filter view."""
        self._enable_sort(False)
        for row in self._filter:
            row[2] = True
        self._enable_sort()
        self._update_labels()

    def _on_enable_none(self, _):
        """Disable all channels in current filter view."""
        self._enable_sort(False)
        for row in self._filter:
            row[1] = False
            row[2] = False
        self._enable_sort()
        self._update_labels()

    def _on_invert(self, _):
        """Invert enabled in current filter view."""
        self._enable_sort(False)
        for row in self._filter:
            if row[2]:
                row[1] = False
                row[2] = False
            else:
                row[2] = True
        self._enable_sort()
        self._update_labels()

    def _refresh_done(self, fut):
        try:
            if fut.exception():
                coro_exception_handler(fut)
            else:
                self._store.clear()
                self._add_model_data()
                self._update_labels()
        finally:
            if self._dialog is not None:
                self._dialog.set_sensitive(True)

    def _on_refresh(self, _):
        """Refresh followed list."""
        self._dialog.set_sensitive(False)
        coro = self._gui_manager.app.api_manager.refresh_followed_channels()
        loop = self._gui_manager.app.api_manager.loop
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        fut.add_done_callback(self._refresh_done)
