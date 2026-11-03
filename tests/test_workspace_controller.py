# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from types import SimpleNamespace

import pytest
from pyqtgraph.Qt import QtGui, QtWidgets

from attractors.console.jupyter_console_panel import JupyterConsolePanel
from attractors.console.workspace_controller import WorkspaceController
from attractors.ui.docking import DockLayout


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    return app


class _SystemToolbarDouble:
    def __init__(self):
        self.plots = []
        self.current_key = None
        self.live_traces = None
        self.status = ""

    def set_plots(self, items, current_key):
        self.plots = [(item["kind"], item["name"]) for item in items]
        self.current_key = current_key

    def set_live_traces(self, plot_name, traces):
        self.live_traces = (plot_name, traces)

    def set_status(self, text):
        self.status = str(text)


class _LivePlotControllerDouble:
    def __init__(self, panel):
        self.panel = panel
        self.renames = []
        self.synced_live_menus = []

    def tooltip(self, plot_name):
        return f"{plot_name}: no live traces"

    def sync_menu(self, plot_name):
        self.synced_live_menus.append(plot_name)

    def rename_plot(self, old_name, new_name):
        self.renames.append((old_name, new_name))
        self.panel.plots.rename(old_name, new_name)

    def clear_plot(self):
        self.panel.plots.clear()

    def clear_all(self):
        self.panel.plots.clear_all()


class _WorkspaceToolbarDouble:
    def __init__(self):
        self.view_combo = QtWidgets.QComboBox()
        self.name_edit = QtWidgets.QLineEdit()
        self.grid_action = QtGui.QAction()
        self.grid_action.setCheckable(True)
        self.crosshair_action = QtGui.QAction()
        self.crosshair_action.setCheckable(True)
        self.explore_syncs = 0

    def sync_explore(self):
        self.explore_syncs += 1


def _workspace_window(panel):
    window = SimpleNamespace()
    window.jupyter_console_panel = panel
    window.system_toolbar = _SystemToolbarDouble()
    window.live_plot_controller = _LivePlotControllerDouble(panel)
    return window


def _find_combo_data(combo, data):
    """Bypass Qt's internal tuple search and do comparison in plain Python"""
    for index in range(combo.count()):
        if combo.itemData(index) == data:
            return index

    return -1


def test_workspace_controller_syncs_2d_and_3d_views(qapp, tmp_path):
    dock_window = QtWidgets.QMainWindow()
    panel = JupyterConsolePanel(DockLayout(dock_window), dict, script_dir=tmp_path)
    panel.plots.new("2D Test", activate=False)
    panel.views3d.new("3D Test", activate=False)

    window = _workspace_window(panel)
    toolbar = _WorkspaceToolbarDouble()
    controller = WorkspaceController(
        panel, toolbar, window.system_toolbar, window.live_plot_controller
    )

    controller.sync_views()

    labels = [toolbar.view_combo.itemText(i) for i in range(toolbar.view_combo.count())]

    assert labels == ["Plot", "2D Test", "3D: 3D View", "3D: 3D Test"]
    assert toolbar.view_combo.currentData() == ("plot", "Plot")
    assert toolbar.name_edit.text() == "Plot"
    assert window.system_toolbar.plots == [
        ("plot", "Plot"),
        ("plot", "2D Test"),
        ("view3d", "3D View"),
        ("view3d", "3D Test"),
    ]


def test_workspace_controller_selected_3d_view_from_toolbar(qapp, tmp_path):
    dock_window = QtWidgets.QMainWindow()
    panel = JupyterConsolePanel(DockLayout(dock_window), dict, script_dir=tmp_path)
    panel.views3d.new("3D Test", activate=False)

    window = _workspace_window(panel)
    toolbar = _WorkspaceToolbarDouble()
    controller = WorkspaceController(
        panel, toolbar, window.system_toolbar, window.live_plot_controller
    )
    toolbar.view_combo.currentIndexChanged.connect(
        lambda _index: controller.on_toolbar_view_selected()
    )

    controller.sync_views()

    index = _find_combo_data(toolbar.view_combo, ("view3d", "3D Test"))
    assert index >= 0
    toolbar.view_combo.setCurrentIndex(index)

    assert panel.active_view_key() == ("view3d", "3D Test")
    assert toolbar.name_edit.text() == "3D Test"
    assert toolbar.explore_syncs == 1
    assert window.system_toolbar.live_traces == ("", [])


def test_workspace_controller_2d_renames(qapp, tmp_path):
    dock_window = QtWidgets.QMainWindow()
    panel = JupyterConsolePanel(DockLayout(dock_window), dict, script_dir=tmp_path)
    panel.plots.new("2D Test")

    window = _workspace_window(panel)
    toolbar = _WorkspaceToolbarDouble()
    controller = WorkspaceController(
        panel, toolbar, window.system_toolbar, window.live_plot_controller
    )
    controller.sync_views()

    toolbar.name_edit.setText("New 2D Test")
    controller.rename_current_view()

    assert panel.plots.names() == ["Plot", "New 2D Test"]
    assert window.live_plot_controller.renames == [("2D Test", "New 2D Test")]


def test_workspace_controller_grid_action_3d_sync(qapp, tmp_path):
    dock_window = QtWidgets.QMainWindow()
    panel = JupyterConsolePanel(DockLayout(dock_window), dict, script_dir=tmp_path)
    panel.views3d.new("A", activate=False)
    panel.views3d.new("B", activate=False)

    view_a = panel.views3d.get("A", activate=False)
    view_b = panel.views3d.get("B", activate=False)
    view_a.grid(False)
    view_b.grid(True)

    window = _workspace_window(panel)
    toolbar = _WorkspaceToolbarDouble()
    controller = WorkspaceController(
        panel, toolbar, window.system_toolbar, window.live_plot_controller
    )
    toolbar.view_combo.currentIndexChanged.connect(
        lambda _index: controller.on_toolbar_view_selected()
    )

    controller.sync_views()

    index_a = _find_combo_data(toolbar.view_combo, ("view3d", "A"))
    assert index_a >= 0
    toolbar.view_combo.setCurrentIndex(index_a)

    assert panel.active_view_key() == ("view3d", "A")
    assert toolbar.grid_action.isChecked() is False
    assert view_a.grid_visible() is False

    index_b = _find_combo_data(toolbar.view_combo, ("view3d", "B"))
    assert index_b >= 0
    toolbar.view_combo.setCurrentIndex(index_b)

    assert panel.active_view_key() == ("view3d", "B")
    assert toolbar.grid_action.isChecked() is True
    assert view_b.grid_visible() is True
    assert view_a.grid_visible() is False
