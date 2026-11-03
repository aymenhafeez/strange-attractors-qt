# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtGui, QtWidgets

from .main_toolbar import make_action
from .style import MENUBAR


class MainMenuBar(QtWidgets.QMenuBar):
    def __init__(
        self,
        toolbar,
        panels_menu,
        signal_dock_action,
        trajectory_dock_action,
        plot_item,
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet(MENUBAR)

        # add toolbar actions to the menu bar directly so they don't need manual syncing
        self.output_panel_action = make_action(
            self, "Output panel", "view-split-top-bottom", checked=False
        )
        self.status_bar_action = make_action(self, "Status bar", checked=False)
        self.panel_actions = {
            name: make_action(self, text, checked=False)
            for name, text in (
                ("lyapunov_panel", "Lyapunov spectrum"),
                ("projection_panel", "Projection heatmaps"),
                ("poincare_panel", "Poincare section"),
                ("bifurcation_panel", "Bifurcation diagram"),
            )
        }
        self.reset_layout_action = make_action(self, "Reset current layout")

        file_menu = self.addMenu("&File")
        self.save_view_action = file_menu.addAction("Save view as PNG")
        file_menu.addSeparator()
        self.open_preset_folder_action = file_menu.addAction("Open preset folder")
        file_menu.addSeparator()
        self.welcome_action = file_menu.addAction("Welcome")
        self.help_action = file_menu.addAction("Help")

        view_menu = self.addMenu("&View")
        view_menu.addActions(
            [
                toolbar.left_panel_action,
                toolbar.right_panel_action,
                self.output_panel_action,
                self.status_bar_action,
            ]
        )
        view_menu.addMenu(panels_menu)
        view_menu.addAction(self.reset_layout_action)
        view_menu.addSeparator()
        self.reset_camera_action = view_menu.addAction("Reset camera")
        self.fit_view_action = view_menu.addAction("Fit view")
        view_menu.addAction(toolbar.grid_action)
        view_menu.addSeparator()
        self.theme_actions = self._add_choice_menu(
            view_menu,
            "Plot theme",
            {None: "System", "light": "Light", "dark": "Dark"},
        )
        view_menu.addSeparator()
        self.reset_session_action = view_menu.addAction("Reset session state")

        system_menu = self.addMenu("&System")
        self.solve_action = system_menu.addAction("Solve")
        self.reset_parameters_action = system_menu.addAction("Reset parameters")
        self.animation_mode_actions = self._add_choice_menu(
            system_menu,
            "Animation mode",
            {"trajectory": "Trajectory", "particle": "Particle flow"},
        )
        system_menu.addSeparator()
        system_menu.addActions(
            [
                toolbar.loop_action,
                toolbar.point_action,
                toolbar.line_action,
                toolbar.trail_action,
            ]
        )

        workspace_menu = self.addMenu("&Workspace")
        self.workspace_mode_actions = self._add_choice_menu(
            workspace_menu, "Mode", {"system": "System", "explore": "Explore"}
        )
        workspace_menu.addSeparator()
        self.summary_action = workspace_menu.addAction("Summary")
        self.explore_workspace_action = workspace_menu.addAction("Explore workspace")
        workspace_menu.addAction(self.reset_layout_action)
        self.examples_menu = workspace_menu.addMenu("Examples")
        workspace_menu.addSeparator()
        self.new_plot_action = workspace_menu.addAction("New plot")
        self.clear_view_action = workspace_menu.addAction("Clear current view")
        self.export_table_action = workspace_menu.addAction("Export current table")
        self.clear_all_views_action = workspace_menu.addAction("Clear all views")
        workspace_menu.addSeparator()
        self.clear_sliders_action = workspace_menu.addAction("Clear sliders")
        self.clear_traces_action = workspace_menu.addAction("Clear traces")
        self.clear_explore_action = workspace_menu.addAction("Clear explore state")
        workspace_menu.addSeparator()
        self._add_plot_actions(workspace_menu, plot_item)
        workspace_menu.addSeparator()
        self._add_proxy_menu(workspace_menu, "Plot options", plot_item.getMenu())
        self._add_proxy_menu(
            workspace_menu, "ViewBox options", plot_item.getViewBox().menu
        )
        workspace_menu.addSeparator()
        self.system_summary_action = workspace_menu.addAction("System summary")
        self.workspace_summary_action = workspace_menu.addAction("Workspace summary")
        workspace_menu.addSeparator()
        self.system_help_action = workspace_menu.addAction("System help")
        self.workspace_help_action = workspace_menu.addAction("Workspace help")

        analysis_menu = self.addMenu("&Analysis")
        signal_dock_action.setText("Signal and spectrum")
        trajectory_dock_action.setText("Trajectory comparison")
        analysis_menu.addActions(
            [
                signal_dock_action,
                trajectory_dock_action,
                *self.panel_actions.values(),
                toolbar.system_action,
            ]
        )

        _hide_menu_icons(self)

    def _add_choice_menu(self, menu, title, choices):
        submenu = menu.addMenu(title)
        group = QtGui.QActionGroup(self)
        actions = {}
        for value, text in choices.items():
            actions[value] = make_action(group, text, checked=not actions)
            submenu.addAction(actions[value])
        return actions

    def _add_plot_actions(self, menu, plot_item):
        view_box = plot_item.getViewBox()
        menu.addAction("View all").triggered.connect(view_box.autoRange)

        mouse_group = QtGui.QActionGroup(self)
        for text, mode in (("Pan", "pan"), ("Zoom", "rect")):
            action = make_action(mouse_group, text, checked=mode == "pan")
            action.triggered.connect(
                lambda _checked=False, mode=mode: view_box.setLeftButtonAction(mode)
            )
            menu.addAction(action)
        menu.addSeparator()

        for text, check in (
            ("X grid", plot_item.ctrl.xGridCheck),
            ("Y grid", plot_item.ctrl.yGridCheck),
        ):
            action = make_action(self, text, checked=check.isChecked())
            action.toggled.connect(check.setChecked)
            check.toggled.connect(action.setChecked)
            menu.addAction(action)

    def _add_proxy_menu(self, parent_menu, title, source_menu):
        menu = parent_menu.addMenu(title)
        source_actions = source_menu.actions()
        if any(isinstance(a, QtWidgets.QWidgetAction) for a in source_actions):
            menu.addAction(
                f"Open {source_menu.title()}...",
                lambda _checked=False: source_menu.popup(QtGui.QCursor.pos()),
            )
            return

        for source_action in source_actions:
            if source_action.isSeparator():
                menu.addSeparator()
            elif source_action.menu() is not None:
                self._add_proxy_menu(menu, source_action.text(), source_action.menu())
            else:
                action = menu.addAction(source_action.text())
                action.setCheckable(source_action.isCheckable())
                action.setChecked(source_action.isChecked())
                action.setEnabled(source_action.isEnabled())
                action.triggered.connect(source_action.trigger)


def _hide_menu_icons(menu):
    for action in menu.actions():
        action.setIconVisibleInMenu(False)
        if action.menu() is not None:
            _hide_menu_icons(action.menu())
