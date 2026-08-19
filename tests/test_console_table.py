from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from pyqtgraph.Qt import QtCore, QtWidgets

from attractors.app import Window
from attractors.console.jupyter_console_panel import JupyterConsolePanel
from attractors.console.table import (
    ConsoleTable,
    ConsoleTableManager,
    ConsoleTableModel,
    normalise_table_data,
)
from attractors.console.workspace_inspector import (
    WorkspaceInspector,
)
from attractors.ui.docking import AreaBoundDock as Dock
from attractors.ui.docking import AreaBoundDockArea


class SettingsDouble:
    def __init__(self):
        self.values = {}

    def setValue(self, key, value):
        self.values[key] = value

    def value(self, key, default=None, type=None):
        return self.values.get(key, default)

    def remove(self, key):
        self.values.pop(key, None)


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    return app


def table_manager():
    dock_area = AreaBoundDockArea()
    table = ConsoleTable()
    dock = Dock("Table", size=(10, 6), closable=False)
    dock.addWidget(table.host)
    dock_area.addDock(dock)

    return ConsoleTableManager(dock_area, "Table", table, dock)


def test_workspace_shell_persists_table_names(qapp):
    panel = JupyterConsolePanel(dict)
    panel.tables.new("Test table", activate=False)

    settings = SettingsDouble()
    window = SimpleNamespace(jupyter_console_panel=panel)

    Window._save_workspace_shell(window, settings)

    restored_panel = JupyterConsolePanel(dict)
    restored_window = SimpleNamespace(jupyter_console_panel=restored_panel)

    Window._restore_workspace_shell(restored_window, settings)

    assert restored_panel.tables.names() == ["Table", "Test table"]
    assert restored_panel.tables.current_name == "Table"


def test_normalise_table_copies_df():
    data = pd.DataFrame({"a": [1, 2], "b": [2, 3]})

    table = normalise_table_data(data)

    assert table.equals(data)
    assert table is not data


def test_normalise_table_converts_series_to_frame():
    data = pd.Series([1, 2], name="test", index=["a", "b"])

    table = normalise_table_data(data)

    assert table.to_dict("list") == {"test": [1, 2]}
    assert table.index.to_list() == ["a", "b"]


def test_noramlise_table_converts_unamed_to_value_column():
    table = normalise_table_data(pd.Series([1, 2]))

    assert table.to_dict("list") == {"value": [1, 2]}


def test_normalise_table_converts_scalar_mapping():
    table = normalise_table_data({"a": 1, "b": 2})

    assert table.to_dict("index") == {"a": {"value": 1}, "b": {"value": 2}}


def test_normalise_table_converts_records():
    table = normalise_table_data([{"a": 1, "b": 2}, {"a": 3, "b": 4}])

    assert table.to_dict("records") == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


def test_normalise_table_converts_scaler():
    table = normalise_table_data(12)

    assert table.to_dict("records") == [{"value": 12}]


def test_normalise_table_converts_1d_array():
    table = normalise_table_data(np.array([1, 2, 3]))

    assert table.to_dict("list") == {"value": [1, 2, 3]}


def test_normalise_table_converts_2d_array():
    table = normalise_table_data(np.array([[1, 2], [3, 4]]))

    assert table.to_dict("list") == {"0": [1, 3], "1": [2, 4]}


def test_normalise_table_rejects_higher_dim_array():
    with pytest.raises(ValueError, match="1D or 2D"):
        normalise_table_data(np.zeros((2, 2, 2)))


def test_console_table_displays_values_and_headers(qapp):
    frame = pd.DataFrame({"a": [1.0, np.nan], "b": ["x", "y"]}, index=["r1", "r2"])
    model = ConsoleTableModel(frame)

    assert model.rowCount() == 2
    assert model.columnCount() == 2

    assert (
        model.headerData(
            0,
            QtCore.Qt.Orientation.Horizontal,
            QtCore.Qt.ItemDataRole.DisplayRole,
        )
        == "a"
    )
    assert (
        model.headerData(
            1,
            QtCore.Qt.Orientation.Vertical,
            QtCore.Qt.ItemDataRole.DisplayRole,
        )
        == "r2"
    )

    assert model.data(model.index(0, 0), QtCore.Qt.ItemDataRole.DisplayRole) == "1.0"
    assert model.data(model.index(1, 0), QtCore.Qt.ItemDataRole.DisplayRole) == ""
    assert model.data(model.index(0, 1), QtCore.Qt.ItemDataRole.DisplayRole) == "x"


def test_console_table_model_read_only(qapp):
    model = ConsoleTableModel(pd.DataFrame({"a": [1]}))
    flags = model.flags(model.index(0, 0))

    assert flags & QtCore.Qt.ItemFlag.ItemIsEnabled
    assert flags & QtCore.Qt.ItemFlag.ItemIsSelectable
    assert not flags & QtCore.Qt.ItemFlag.ItemIsEditable


def test_console_table_model_sets_and_clears_data(qapp):
    table = ConsoleTable()

    result = table.set_data({"a": [1, 2]})

    assert result is table
    assert table.model.rowCount() == 2
    assert table.model.columnCount() == 1
    assert table.dataframe().to_dict("list") == {"a": [1, 2]}

    table.clear()

    assert table.model.rowCount() == 0
    assert table.model.columnCount() == 0


def test_console_table_manager_creates_and_selects_tables(qapp):
    manager = table_manager()

    table = manager.new("Summary")
    table.set_data({"a": [1, 2]})

    assert manager.names() == ["Table", "Summary"]
    assert manager.current_name == "Summary"
    assert manager.current is table
    assert manager.current.dataframe().to_dict("list") == {"a": [1, 2]}


def test_console_table_manager_shows_updates_named_table(qapp):
    manager = table_manager()

    table = manager.show({"a": [1, 2]}, name="Summary")

    assert manager.current_name == "Summary"
    assert table.dataframe().to_dict("list") == {"a": [1, 2]}

    result = manager.show({"b": [3]}, name="Summary")

    assert result is table
    assert table.dataframe().to_dict("list") == {"b": [3]}


def test_console_table_manager_rename_and_clse(qapp):
    manager = table_manager()
    manager.new("Summary", activate=False)

    manager.rename("Summary", "New table")

    assert manager.names() == ["Table", "New table"]

    manager.close("New table")

    assert manager.names() == ["Table"]


def test_console_manager_close_default_clears(qapp):

    manager = table_manager()
    manager.show({"a": [1, 2]})

    manager.close("Table")

    assert manager.names() == ["Table"]
    assert manager.current_name == "Table"
    assert manager.current.dataframe().empty


def test_console_panel_exposes_table_manager(qapp):
    panel = JupyterConsolePanel(dict)
    result = panel.tables.show({"a": [1, 2]}, name="Test table")

    assert panel.tables.names() == ["Table", "Test table"]
    assert panel.tables.current_name == "Test table"
    assert result.dataframe().to_dict("list") == {"a": [1, 2]}

    panel.tables.close("Test table")

    assert panel.tables.names() == ["Table"]


def test_workspace_inspector_shows_help_table(qapp):
    panel = JupyterConsolePanel(dict)
    inspector = WorkspaceInspector(panel)

    data = inspector.help(table=True)

    assert "Workspace help" in panel.tables.names()
    assert panel.tables.current_name == "Workspace help"
    assert panel.tables.current.dataframe().equals(data)


def test_workspace_inspector_shows_views_table(qapp):
    panel = JupyterConsolePanel(dict)
    panel.plots.new("Plot test", activate=False)
    panel.views3d.new("3D test", activate=False)

    inspector = WorkspaceInspector(panel)

    data = inspector.views(table=True)

    assert "Workspace views" in panel.tables.names()
    assert panel.tables.current.dataframe().equals(data)


def test_workspace_inepector_shows_summary_table(qapp):
    panel = JupyterConsolePanel(dict)
    inspector = WorkspaceInspector(panel)

    data = inspector.summary(table=True)

    assert "Workspace summary" in panel.tables.names()
    assert panel.tables.current.dataframe()["value"].equals(data)


def test_console_table_exports_csv(tmp_path, qapp):
    table = ConsoleTable()
    table.set_data({"a": [1, 2], "b": ["x", "y"]})

    path = table.to_csv(tmp_path / "table.csv", index=False)

    assert path == tmp_path / "table.csv"
    assert path.read_text() == "a,b\n1,x\n2,y\n"


def test_console_table_manager_exports_named_table(tmp_path, qapp):
    manager = table_manager()
    manager.show({"a": [1, 2]}, name="TestTable")
    manager.show({"b": [3, 4]}, name="AnotherTable")

    path = manager.export(tmp_path / "test.csv", name="TestTable", index=False)

    assert path == tmp_path / "test.csv"
    assert path.read_text() == "a\n1\n2\n"
    assert manager.current_name == "AnotherTable"


def test_export_current_table_from_menu(tmp_path, qapp, monkeypatch):
    panel = JupyterConsolePanel(dict)
    panel.tables.show({"a": [1, 2]}, name="Test")

    path = tmp_path / "test.csv"
    statuses = []
    window = SimpleNamespace(
        jupyter_console_panel=panel,
        _set_app_status=lambda text, error=False: statuses.append((text, error)),
    )

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(path), "CSV (*.csv)"),
    )

    Window._export_current_table(window)

    assert path.read_text() == "a\n1\n2\n"
    assert statuses == [(f"Exported table to {path}", False)]


def test_export_current_table_ignores_cancel(qapp, monkeypatch):
    panel = JupyterConsolePanel(dict)
    statuses = []
    window = SimpleNamespace(
        jupyter_console_panel=panel,
        _set_app_status=lambda text, error=False: statuses.append((text, error)),
    )

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )

    Window._export_current_table(window)

    assert statuses == []
