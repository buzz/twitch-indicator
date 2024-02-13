import logging
from typing import TYPE_CHECKING, Any, Optional, cast

from gi.repository import Gtk

from twitch_indicator.state import ChannelState
from twitch_indicator.utils import get_data_filepath

if TYPE_CHECKING:
    from twitch_indicator.gui.gui_manager import GuiManager


class ChannelChooserDialog:
    """Twitch indicator channel chooser dialog."""

    def __init__(self, gui_manager: "GuiManager") -> None:
        self._logger = logging.getLogger(__name__)
        self._gui_manager = gui_manager
        self._reset_attributes()

    def _reset_attributes(self) -> None:
        self._dialog: Optional[Gtk.Dialog] = None
        self._list_view: Optional[Gtk.TreeView] = None
        self._search_text: str = ""
        self._label_followed: Optional[Gtk.Label] = None
        self._label_enabled: Optional[Gtk.Label] = None
        self._store: Optional[Gtk.ListStore] = None
        self._filter: Optional[Gtk.TreeModelFilter] = None

    def show(self, settings_dialog: Gtk.Dialog) -> None:
        """Shows channel chooser dialog."""
        if self._dialog:
            self._dialog.present()
            return

        # dialog
        title = "Choose channels"
        self._dialog = Gtk.Dialog(title=title, transient_for=settings_dialog)
        self._dialog.set_border_width(10)
        self._dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self._dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        # builder
        builder = Gtk.Builder()
        builder.add_from_file(get_data_filepath("twitch-indicator-channel-chooser.glade"))

        # get widgets
        content_box = cast(Gtk.Box, builder.get_object("content_box"))
        self._label_followed = cast(Gtk.Label, builder.get_object("label_followed"))
        self._label_enabled = cast(Gtk.Label, builder.get_object("label_enabled"))
        self._list_view = cast(Gtk.TreeView, builder.get_object("list_view"))
        entry_search = cast(Gtk.Entry, builder.get_object("entry_search"))
        btn_enable_all = cast(Gtk.Button, builder.get_object("btn_enable_all"))
        btn_enable_none = cast(Gtk.Button, builder.get_object("btn_enable_none"))
        btn_invert = cast(Gtk.Button, builder.get_object("btn_invert"))

        # store
        # columns: (channel username, enabled, channel_id)
        self._store = Gtk.ListStore(str, bool, int)
        self._store.set_default_sort_func(self._sort_func)
        self._enable_sort()
        self._filter = self._store.filter_new()
        self._filter.set_visible_func(self._filter_func)

        # chanel list view
        self._list_view.get_selection().set_mode(Gtk.SelectionMode.NONE)
        self._list_view.set_model(self._filter)
        self._list_view.set_activate_on_single_click(True)

        # channel name column
        name_renderer = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn(title="Streamer", cell_renderer=name_renderer)
        col_name.add_attribute(name_renderer, "text", 0)
        col_name.set_expand(True)
        self._list_view.append_column(col_name)

        # channel enabled column
        enabled_renderer = Gtk.CellRendererToggle()
        col_enabled = Gtk.TreeViewColumn(title="Enabled", cell_renderer=enabled_renderer)
        col_enabled.add_attribute(enabled_renderer, "active", 1)
        col_enabled.set_expand(False)
        self._list_view.append_column(col_enabled)

        # add layout to dialog
        box = self._dialog.get_content_area()
        box.add(content_box)

        # signals
        self._list_view.connect("row-activated", self._on_enabled_toggled)
        entry_search.connect("changed", self._on_search_changed)
        btn_enable_all.connect("clicked", self._on_enable_all)
        btn_enable_none.connect("clicked", self._on_enable_none)
        btn_invert.connect("clicked", self._on_invert)

        self._add_model_data()
        self._update_labels()
        self._list_view.show_all()
        self._dialog.show_all()

        if self._dialog.run() == Gtk.ResponseType.OK:
            self._commit_model_data()

        self.destroy()

    def destroy(self) -> None:
        """Destroy dialog window."""
        if self._dialog is not None:
            self._dialog.destroy()
        self._reset_attributes()

    def present(self) -> None:
        """Move dialog window to front."""
        if self._dialog:
            self._dialog.present()

    @property
    def _enabled_count(self) -> int:
        if self._store is None:
            return 0
        return sum(1 for row in self._store if row[1])

    def _add_model_data(self) -> None:
        """Copy channel data from app state to local model."""
        if self._store is None:
            raise RuntimeError("Store is None")

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
        if self._store is None:
            raise RuntimeError("Store is None")

        enabled_channel_ids = {
            cast(str, row[2]): ChannelState.ENABLED if row[1] else ChannelState.DISABLED
            for row in self._store
        }
        self._gui_manager.app.state.set_enabled_channel_ids(enabled_channel_ids)

    def _update_labels(self) -> None:
        """Update count labels."""
        if (
            self._store is not None
            and self._label_followed is not None
            and self._label_enabled is not None
        ):
            self._label_followed.set_markup(f"Followed: <b>{len(self._store)}</b>")
            self._label_enabled.set_markup(f"Enabled: <b>{self._enabled_count}</b>")

    def _enable_sort(self, enabled=True) -> None:
        """Enable/disable sorting."""
        if self._store is not None:
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
        if self._filter is not None:
            self._filter[path][1] = not self._filter[path][1]
            self._update_labels()

    def _on_search_changed(self, entry: Gtk.Entry) -> None:
        """Update search phrase and refilter list."""
        if self._filter is not None:
            self._search_text = entry.get_text().lower()
            self._filter.refilter()

    def _on_enable_all(self, btn: Gtk.Button) -> None:
        """Enable all channels in current filter view."""
        if self._filter is not None:
            self._enable_sort(False)
            for row in self._filter:
                row[1] = True
            self._enable_sort()
            self._update_labels()

    def _on_enable_none(self, btn: Gtk.Button) -> None:
        """Disable all channels in current filter view."""
        if self._filter is not None:
            self._enable_sort(False)
            for row in self._filter:
                row[1] = False
            self._enable_sort()
            self._update_labels()

    def _on_invert(self, btn: Gtk.Button) -> None:
        """Invert enabled in current filter view."""
        if self._filter is not None:
            self._enable_sort(False)
            for row in self._filter:
                row[1] = not row[1]
            self._enable_sort()
            self._update_labels()
