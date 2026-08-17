from types import SimpleNamespace

import pytest
from pyqtgraph.Qt import QtWidgets

from attractors.console.jupyter_console_panel import JupyterConsolePanel
from attractors.console.workspace_controller import WorkspaceController


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

    def _plot_combo_tooltip(self, plot_name):
        return f"{plot_name}: no live traces"

    def _sync_live_menu(self, plot_name):
        self.synced_live_menus.append(plot_name)

    def rename_plot(self, old_name, new_name):
        self.renames.append((old_name, new_name))
        self.panel.plots.rename(old_name, new_name)

    def _clear_plots(self):
        self.panel.plots.clear()

    def _clear_all_plots(self):
        self.panel.plots.clear_all()


def _workspace_window(panel):
    window = SimpleNamespace()
    window.jupyter_console_panel = panel
    window.toolbar_workspace_combo = QtWidgets.QComboBox()
    window.toolbar_workspace_name = QtWidgets.QLineEdit()
    window.system_toolbar = _SystemToolbarDouble()
    window.live_plot_controller = _LivePlotControllerDouble(panel)
    window.explore_syncs = 0
    window.workspace_syncs = 0
    window._sync_jupyter_workspace_state = lambda: setattr(
        window, "workspace_syncs", window.workspace_syncs + 1
    )
    window._sync_explore_actions = lambda: setattr(
        window, "explore_syncs", window.explore_syncs + 1
    )
    return window


def _find_combo_data(combo, data):
    """Bypass Qt's internal tuple search and do comparison in plain Python"""
    for index in range(combo.count()):
        if combo.itemData(index) == data:
            return index

    return -1


def test_workspace_controller_syncs_2d_and_3d_views(qapp):
    panel = JupyterConsolePanel(dict)
    panel.plots.new("2D Test", activate=False)
    panel.views3d.new("3D Test", activate=False)

    window = _workspace_window(panel)
    controller = WorkspaceController(window)

    controller.sync_views()

    labels = [
        window.toolbar_workspace_combo.itemText(i)
        for i in range(window.toolbar_workspace_combo.count())
    ]

    assert labels == ["Plot", "2D Test", "3D: 3D View", "3D: 3D Test"]
    assert window.toolbar_workspace_combo.currentData() == ("plot", "Plot")
    assert window.toolbar_workspace_name.text() == "Plot"
    assert window.system_toolbar.plots == [
        ("plot", "Plot"),
        ("plot", "2D Test"),
        ("view3d", "3D View"),
        ("view3d", "3D Test"),
    ]


def test_workspace_controller_selected_3d_view_from_toolbar(qapp):
    panel = JupyterConsolePanel(dict)
    panel.views3d.new("3D Test", activate=False)

    window = _workspace_window(panel)
    controller = WorkspaceController(window)
    window.toolbar_workspace_combo.currentIndexChanged.connect(
        lambda _index: controller.on_toolbar_view_selected()
    )

    controller.sync_views()

    index = _find_combo_data(window.toolbar_workspace_combo, ("view3d", "3D Test"))
    assert index >= 0
    window.toolbar_workspace_combo.setCurrentIndex(index)

    assert panel.active_view_key() == ("view3d", "3D Test")
    assert window.toolbar_workspace_name.text() == "3D Test"
    assert window.explore_syncs == 1
    assert window.system_toolbar.live_traces == ("", [])


def test_workspace_controller_2d_renames(qapp):
    panel = JupyterConsolePanel(dict)
    panel.plots.new("2D Test")

    window = _workspace_window(panel)
    controller = WorkspaceController(window)
    controller.sync_views()

    window.toolbar_workspace_name.setText("New 2D Test")
    controller.rename_current_view()

    assert panel.plots.names() == ["Plot", "New 2D Test"]
    assert window.live_plot_controller.renames == [("2D Test", "New 2D Test")]
