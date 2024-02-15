import logging
from typing import TYPE_CHECKING, Any, cast

from gi.repository import Gtk

from twitch_indicator.gui.dialogs.base import BaseDialog
from twitch_indicator.state import ChannelState

if TYPE_CHECKING:
    from twitch_indicator.gui.gui_manager import GuiManager


class ChannelChooserDialog(BaseDialog[Gtk.Dialog]):
    """Twitch indicator channel chooser dialog."""

    def __init__(self, gui_manager: "GuiManager") -> None:
        super().__init__("channel-chooser", gui_manager)
        self._logger = logging.getLogger(__name__)
        self._search_text = ""

        # Get widgets
        self._label_followed = cast(Gtk.Label, self._builder.get_object("label_followed"))
        self._label_enabled = cast(Gtk.Label, self._builder.get_object("label_enabled"))
        self._list_view = cast(Gtk.TreeView, self._builder.get_object("list_view"))
        self._entry_search = cast(Gtk.Entry, self._builder.get_object("entry_search"))
        self._btn_enable_all = cast(Gtk.Button, self._builder.get_object("btn_enable_all"))
        self._btn_enable_none = cast(Gtk.Button, self._builder.get_object("btn_enable_none"))
        self._btn_invert = cast(Gtk.Button, self._builder.get_object("btn_invert"))

        self._setup_events()

    def run(self) -> None:
        """Run channel chooser dialog."""
        self._setup_store()
        self._add_model_data()
        self._update_labels()
        self._dialog.show_all()

        # Run dialog
        if self._dialog.run() == Gtk.ResponseType.OK:
            self._commit_model_data()

        self.destroy()

    def _setup_store(self):
        """Setup list model."""
        # Columns: (channel username, enabled, channel_id)
        self._store = Gtk.ListStore(str, bool, int)
        self._store.set_default_sort_func(self._sort_func)
        self._enable_sort()
        self._list_filter = self._store.filter_new()
        self._list_filter.set_visible_func(self._filter_func)

        # List view
        self._list_view.set_model(self._list_filter)
        self._list_view.set_activate_on_single_click(True)

        # Name column
        name_renderer = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn(title="Streamer", cell_renderer=name_renderer)
        col_name.add_attribute(name_renderer, "text", 0)
        col_name.set_expand(True)
        self._list_view.append_column(col_name)

        # Enabled column
        enabled_renderer = Gtk.CellRendererToggle()
        col_enabled = Gtk.TreeViewColumn(title="Enabled", cell_renderer=enabled_renderer)
        col_enabled.add_attribute(enabled_renderer, "active", 1)
        col_enabled.set_expand(False)
        self._list_view.append_column(col_enabled)

    @property
    def _enabled_count(self) -> int:
        return sum(1 for row in self._store if row[1])

    def _add_model_data(self) -> None:
        """Copy data from app state to local model."""
        with self._gui_manager.app.state.locks["enabled_channel_ids"]:
            with self._gui_manager.app.state.locks["followed_channels"]:
                ec_ids = self._gui_manager.app.state.enabled_channel_ids
                for channel in self._gui_manager.app.state.followed_channels:
                    enab = ec_ids.get(channel.broadcaster_id, ChannelState.DISABLED)
                    row = (
                        channel.broadcaster_name,
                        ChannelState.ENABLED == enab,
                        channel.broadcaster_id,
                    )
                    self._store.append(row)

    def _commit_model_data(self) -> None:
        """Store channel data in app state."""
        enabled_channel_ids = {
            cast(str, row[2]): ChannelState.ENABLED if row[1] else ChannelState.DISABLED
            for row in self._store
        }
        self._gui_manager.app.state.set_enabled_channel_ids(enabled_channel_ids)

    def _update_labels(self) -> None:
        """Update count labels."""
        self._label_enabled.set_text(f"Enabled: {self._enabled_count}/{len(self._store)}")

    def _enable_sort(self, enabled=True) -> None:
        """Enable/disable sorting."""
        self._store.set_sort_column_id(
            (
                Gtk.TREE_SORTABLE_DEFAULT_SORT_COLUMN_ID
                if enabled
                else Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID
            ),
            Gtk.SortType.ASCENDING,
        )

    def _sort_func(
        self, model: Gtk.TreeModel, iter1: Gtk.TreeIter, iter2: Gtk.TreeIter, _: Any
    ) -> int:
        """Sort entries by enabled, case-insensitive alphanumeric"""
        name1 = model[iter1][0].lower()
        enabled1 = model[iter1][1]
        name2 = model[iter2][0].lower()
        enabled2 = model[iter2][1]

        if enabled1 and not enabled2:
            return -1
        if not enabled1 and enabled2:
            return 1

        if name1 < name2:
            return -1
        if name1 == name2:
            return 0

        return 1

    def _filter_func(self, model: Gtk.TreeModelFilter, iter: Gtk.TreeIter, _: Any) -> bool:
        """Filter list by search phrase."""
        if self._search_text == "":
            return True
        return self._search_text in model[iter][0].lower()

    def _on_enabled_toggled(
        self, tree_view: Gtk.TreeView, path: Gtk.TreePath, column: Gtk.TreeViewColumn
    ) -> None:
        """Enabled checkbox toggled."""
        self._list_filter[path][1] = not self._list_filter[path][1]
        self._update_labels()

    def _on_search_changed(self, entry: Gtk.Entry) -> None:
        """Update search phrase and refilter list."""
        self._search_text = entry.get_text().lower()
        self._list_filter.refilter()

    def _on_enable_all(self, btn: Gtk.Button) -> None:
        """Enable all channels in current filter view."""
        self._enable_sort(False)
        for row in self._list_filter:
            row[1] = True
        self._enable_sort()
        self._update_labels()

    def _on_disable_all(self, btn: Gtk.Button) -> None:
        """Disable all channels in current filter view."""
        self._enable_sort(False)
        for row in self._list_filter:
            row[1] = False
        self._enable_sort()
        self._update_labels()

    def _on_invert(self, btn: Gtk.Button) -> None:
        """Invert enabled in current filter view."""
        self._enable_sort(False)
        for row in self._list_filter:
            row[1] = not row[1]
        self._enable_sort()
        self._update_labels()
