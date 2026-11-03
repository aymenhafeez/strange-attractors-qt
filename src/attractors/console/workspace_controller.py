# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore


class WorkspaceController:
    def __init__(self, window, toolbar):
        self.window = window
        self.toolbar = toolbar

    @property
    def console_panel(self):
        return self.window.jupyter_console_panel

    @property
    def system_toolbar(self):
        return self.window.system_toolbar

    def sync_views(self):
        combo = self.toolbar.view_combo
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

        kind, name = active_key
        self.toolbar.name_edit.setText(name)
        self.system_toolbar.set_plots(items, active_key)

        if kind == "plot":
            self.window.live_plot_controller._sync_live_menu(name)
        else:
            self.system_toolbar.set_live_traces("", [])

        self.sync_grid_action()
        self.sync_crosshair_action()

    def current_crosshair_visible(self):
        kind, _name = self.console_panel.active_view_key()
        if kind == "view3d":
            return False

        return self.console_panel.plots.crosshair_visible()

    def sync_crosshair_action(self):
        action = self.toolbar.crosshair_action
        kind, _name = self.console_panel.active_view_key()
        with QtCore.QSignalBlocker(action):
            action.setEnabled(kind == "plot")
            action.setChecked(kind == "plot" and self.current_crosshair_visible())

    def set_current_crosshair_visible(self, visible):
        kind, _name = self.console_panel.active_view_key()
        if kind != "plot":
            self.sync_crosshair_action()
            return

        self.console_panel.plots.set_crosshair_visible(visible)

    def on_toolbar_view_selected(self):
        kind, name = self.toolbar.view_combo.currentData()
        self.console_panel.set_active_workspace_view(kind, name)
        self.sync_views()
        self.toolbar.sync_explore()

    def new_plot(self):
        self.console_panel.plots.new()

    def new_view3d(self):
        self.console_panel.views3d.new()

    def rename_current_view(self):
        kind, old_name = self.console_panel.active_view_key()
        new_name = self.toolbar.name_edit.text().strip()
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
            self.system_toolbar.set_status("Cleared current 3D view")
            self.sync_views()
            self.toolbar.sync_explore()

    def clear_all_views(self):
        self.window.live_plot_controller._clear_all_plots()
        self.console_panel.views3d.clear_all()
        self.system_toolbar.set_status("Cleared workspace views")
        self.sync_views()
        self.toolbar.sync_explore()

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
            return self.console_panel.views3d.grid_visible()

        return self.console_panel.plots.grid_visible()

    def sync_grid_action(self):
        with QtCore.QSignalBlocker(self.toolbar.grid_action):
            self.toolbar.grid_action.setChecked(self.current_grid_visible())

    def set_current_grid_visible(self, visible):
        kind, _name = self.console_panel.active_view_key()
        if kind == "view3d":
            self.console_panel.views3d.grid(visible)
        else:
            self.console_panel.plots.set_grid_visible(visible)

    def set_current_view_orbit(self, enabled):
        kind, _name = self.console_panel.active_view_key()
        if kind == "view3d":
            self.console_panel.views3d.orbit(enabled)

    def clear_explore_traces(self):
        self.console_panel.active_explorer().clear_traces()
        self.console_panel.set_explore_visible(True)

    def clear_explore_sliders(self):
        self.console_panel.active_explorer().clear_sliders()
        self.console_panel.set_explore_visible(True)

    def clear_explore(self):
        self.console_panel.active_explorer().clear()
        self.console_panel.set_explore_visible(True)

    def remove_explore_trace(self, name):
        self.console_panel.active_explorer().remove_trace(name)

    def _view_tooltip(self, item):
        if item["kind"] == "view3d":
            return f"{item['label']}: 3D view"

        return self.window.live_plot_controller._plot_combo_tooltip(item["name"])
