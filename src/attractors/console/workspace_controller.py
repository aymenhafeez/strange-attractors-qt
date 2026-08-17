from pyqtgraph.Qt import QtCore


class WorkspaceController:
    def __init__(self, window):
        self.window = window

    @property
    def console_panel(self):
        return self.window.jupyter_console_panel

    @property
    def toolbar(self):
        return self.window.system_toolbar

    def sync_views(self):
        combo = getattr(self.window, "toolbar_workspace_combo", None)
        name_edit = getattr(self.window, "toolbar_workspace_name", None)

        if combo is None or name_edit is None:
            return

        items = self.console_panel.workspace_view_items()
        active_key = self.console_panel.active_view_key()

        with QtCore.QSignalBlocker(combo):
            combo.clear()

            current_index = -1
            for item in items:
                key = (item["kind"], item["name"])
                combo.addItem(item["label"], key)
                combo.setItemData(
                    combo.count() - 1,
                    self._view_tooltip(item),
                    QtCore.Qt.ItemDataRole.ToolTipRole,
                )

                if key == active_key:
                    current_index = combo.count() - 1

            if current_index >= 0:
                combo.setCurrentIndex(current_index)

        _, name = active_key
        name_edit.setText(name)
        self.toolbar.set_plots(items, active_key)

        kind, name = active_key
        if kind == "plot":
            self.window.live_plot_controller._sync_live_menu(name)
        else:
            self.toolbar.set_live_traces("", [])

        self.sync_grid_action()

    def on_toolbar_view_selected(self):
        combo = self.window.toolbar_workspace_combo
        data = combo.currentData()

        if isinstance(data, tuple) and len(data) == 2:
            kind, name = data
            self.console_panel.set_active_workspace_view(kind, name)
            self.sync_views()
            self.window._sync_explore_actions()
            return

        name = combo.currentText().strip()
        if not name:
            return

        self.window.toolbar_workspace_name.setText(name)
        self.console_panel.plots.get(name)

    def new_plot(self):
        self.console_panel.plots.new()
        self.window._sync_jupyter_workspace_state()

    def new_view3d(self):
        self.console_panel.views3d.new()
        self.window._sync_jupyter_workspace_state()

    def rename_current_view(self):
        kind, old_name = self.console_panel.active_view_key()
        new_name = self.window.toolbar_workspace_name.text().strip()
        if not new_name:
            return

        if kind == "view3d":
            self.console_panel.views3d.rename(old_name, new_name)
            self.sync_views()
            return

        self.window.live_plot_controller.rename_plot(old_name, new_name)

    def clear_current_view(self):
        kind, _name = self.console_panel.active_view_key()
        if kind == "plot":
            self.window.live_plot_controller._clear_plot()
        else:
            self.console_panel.views3d.clear()
            self.toolbar.set_status("Cleared current 3D view")
            self.sync_views()
            self.window._sync_explore_actions()

    def clear_all_views(self):
        self.window.live_plot_controller._clear_all_plots()
        self.console_panel.views3d.clear_all()
        self.toolbar.set_status("Cleared workspace views")
        self.sync_views()
        self.window._sync_explore_actions()

    def fit_current_view(self):
        kind, _name = self.console_panel.active_view_key()
        if kind == "view3d":
            self.console_panel.views3d.fit()
        else:
            self.console_panel.plots.auto_range()

    def reset_current_view(self):
        kind, _name = self.console_panel.active_view_key()
        if kind == "view3d":
            self.console_panel.views3d.reset_camera()
        else:
            self.console_panel.plots.auto_range()

    def current_grid_visible(self):
        kind, _name = self.console_panel.active_view_key()
        if kind == "view3d":
            self.console_panel.views3d.grid_visible()
            return self.console_panel.views3d.grid_visible()

        return self.console_panel.plots.grid_visible()

    def sync_grid_action(self):
        action = getattr(self.window, "workspace_grid_action", None)
        if action is None:
            return

        with QtCore.QSignalBlocker(action):
            action.setChecked(self.current_grid_visible())

    def set_current_grid_visible(self, visible):
        kind, _name = self.console_panel.active_view_key()
        if kind == "view3d":
            self.console_panel.views3d.grid(visible)
        else:
            self.console_panel.plots.set_grid_visible(visible)

    def _view_tooltip(self, item):
        if item["kind"] == "view3d":
            return f"{item['label']}: 3D view"

        return self.window.live_plot_controller._plot_combo_tooltip(item["name"])
