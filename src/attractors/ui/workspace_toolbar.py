# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore, QtWidgets

from .icons import icon
from .main_toolbar import make_action


class WorkspaceToolbar:
    def __init__(self, toolbar, system_toolbar, console_panel):
        self._toolbar = toolbar
        self._console_panel = console_panel
        self._explorer = None
        self._mode = None
        self._visible = False
        self._actions = []

        self.system_toolbar_action = toolbar.insertWidget(
            toolbar.right_panel_action, system_toolbar
        )

        label = QtWidgets.QLabel(" View: ")
        label.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._add_widget(label)

        self.view_combo = QtWidgets.QComboBox()
        self.view_combo.setMinimumWidth(50)
        self.view_combo.setMaximumWidth(130)
        self._add_widget(self.view_combo)

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Plot name")
        self.name_edit.setMaximumWidth(130)
        self._add_widget(self.name_edit)

        new_button = QtWidgets.QToolButton()
        new_button.setText("New")
        new_button.setIcon(icon("list-add"))
        new_button.setToolTip("Create a new workspace view")
        new_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        new_menu = QtWidgets.QMenu(new_button)
        self.new_plot_action = new_menu.addAction("New 2D plot")
        self.new_view3d_action = new_menu.addAction("New 3D view")
        new_button.setMenu(new_menu)
        toolbar.no_focus(self._add_widget(new_button))

        self.rename_action = self._add(
            "Rename", "edit-rename", tooltip="Rename the current workspace view"
        )
        self.clear_view_action = self._add(
            "Clear", "edit-clear-history", tooltip="Clear the current view"
        )
        self.clear_all_action = self._add(
            "Clear all", "edit-delete", tooltip="Clear all views"
        )
        self.fit_action = self._add(
            "Fit", "view-fullscreen", tooltip="Fit current view"
        )
        self.reset_action = self._add("Reset", "zoom-original", tooltip="Reset camera")
        self.grid_action = self._add(
            "Grid", "view-grid", tooltip="Toggle grid visibility", checked=True
        )
        self.orbit_action = self._add(
            "Orbit",
            "object-rotate-right",
            tooltip="Toggle current view orbit mode",
            checked=False,
        )
        self.crosshair_action = self._add(
            "Crosshair",
            "crosshairs",
            tooltip="Show plot crosshair coordinates",
            checked=False,
        )

        self.trace_button = QtWidgets.QToolButton()
        self.trace_button.setText("Traces: 0")
        self.trace_button.setToolTip("Manage reactive traces for the current view")
        self.trace_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.trace_menu = QtWidgets.QMenu(self.trace_button)
        self.trace_button.setMenu(self.trace_menu)
        trace_action = self._add_widget(self.trace_button)
        toolbar.no_focus(trace_action)
        self.clear_sliders_action = self._add(
            "Sliders", "edit-clear", tooltip="Clear sliders for the current view"
        )
        self.clear_explore_action = self._add(
            "Explore",
            "edit-delete",
            tooltip="Clear sliders and reactive traces for the current view",
        )
        self._explore_actions = (
            trace_action,
            self.clear_sliders_action,
            self.clear_explore_action,
        )

        for action in (self.system_toolbar_action, *self._actions):
            action.setVisible(False)

        console_panel.active_view_changed.connect(self.sync_explore)
        console_panel.plots.current_changed.connect(lambda _name: self.sync_explore())
        console_panel.views3d.current_changed.connect(lambda _name: self.sync_explore())

    def _add(self, *args, **kwargs):
        action = make_action(self._toolbar, *args, **kwargs)
        self._toolbar.insertAction(self._toolbar.right_panel_action, action)
        self._toolbar.no_focus(action)
        self._actions.append(action)
        return action

    def _add_widget(self, widget):
        action = self._toolbar.insertWidget(self._toolbar.right_panel_action, widget)
        self._actions.append(action)
        return action

    def set_workspace_state(self, mode, visible):
        self._mode = mode
        self._visible = visible
        for action in self._actions:
            action.setVisible(visible)
        self.system_toolbar_action.setVisible(visible and mode == "system")
        self.sync_explore()

    def sync_explore(self):
        explore_visible = self._visible and self._mode == "explore"
        for action in self._explore_actions:
            action.setVisible(explore_visible)

        # disconnet while hidden as well
        explorer = self._console_panel.active_explorer() if explore_visible else None
        if explorer is not self._explorer:
            if self._explorer is not None:
                self._explorer.changed.disconnect(self.sync_explore)
            self._explorer = explorer
            if explorer is not None:
                explorer.changed.connect(self.sync_explore)

        if explorer is None:
            return

        trace_names = explorer.trace_names()
        slider_names = explorer.slider_names()
        self.trace_button.setText(f"Traces: {len(trace_names)}")
        self.clear_sliders_action.setEnabled(bool(slider_names))
        self.clear_explore_action.setEnabled(
            bool(trace_names or slider_names or explorer.animation_names())
        )

        self.trace_menu.clear()
        if not trace_names:
            self.trace_menu.addAction("No traces").setEnabled(False)
        for name in trace_names:
            self.trace_menu.addAction(f"Remove {name}").setData(name)
