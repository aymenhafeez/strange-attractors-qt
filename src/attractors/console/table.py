import numpy as np
import pandas as pd
from pyqtgraph.Qt import QtCore, QtWidgets

from ..ui.docking import AreaBoundDock as Dock


def normalise_table_data(data):
    if isinstance(data, pd.DataFrame):
        return data.copy()

    if isinstance(data, pd.Series):
        name = data.name if data.name is not None else "value"
        return data.rename(name).to_frame()

    if isinstance(data, dict):
        return _normalise_mapping(data)

    if np.isscalar(data):
        return pd.DataFrame({"value": [data]})

    rows = _record_rows(data)
    if rows is not None:
        return pd.DataFrame(rows)

    array = np.asarray(data, dtype="object")

    if array.ndim == 0:
        return pd.DataFrame({"value": [array.item()]})

    if array.ndim == 1:
        return pd.DataFrame({"value": array})

    if array.ndim == 2:
        columns = [str(i) for i in range(array.shape[1])]
        return pd.DataFrame(array, columns=columns)

    raise ValueError("Table data must be scaler, 1D or 2D")


def _record_rows(data):
    if isinstance(data, (str, bytes)):
        return None

    try:
        rows = list(data)
    except TypeError:
        return None

    if rows and all(isinstance(row, dict) for row in rows):
        return rows

    return None


def _normalise_mapping(data):
    if not data:
        return pd.DataFrame()

    try:
        return pd.DataFrame(data)

    except ValueError:
        return pd.DataFrame({"value": data})


class ConsoleTableModel(QtCore.QAbstractTableModel):
    def __init__(self, dataframe=None, parent=None):
        super().__init__(parent)
        self._dataframe = pd.DataFrame() if dataframe is None else dataframe.copy()

    def rowCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0
        return len(self._dataframe)

    def columnCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0
        return len(self._dataframe.columns)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        value = self._dataframe.iat[index.row(), index.column()]
        if pd.isna(value):
            return ""

        return str(value)

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == QtCore.Qt.Orientation.Horizontal:
            return str(self._dataframe.columns[section])

        return str(self._dataframe.index[section])

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags

        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def set_dataframe(self, dataframe):
        self.beginResetModel()
        try:
            self._dataframe = dataframe.copy()
        finally:
            self.endResetModel()

    def dataframe(self):
        return self._dataframe.copy()


class ConsoleTable:
    def __init__(self):
        self.host = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(self.host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.view = QtWidgets.QTableView()
        self.view.setAlternatingRowColors(True)
        self.view.setSortingEnabled(False)
        self.view.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.view.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.model = ConsoleTableModel(parent=self.view)
        self.view.setModel(self.model)

        self.layout.addWidget(self.view)

    def __repr__(self):
        rows = self.model.rowCount()
        columns = self.model.columnCount()

        return f"ConsoleTable(rows={rows}, columns={columns})"

    def set_data(self, data):
        dataframe = normalise_table_data(data)
        self.model.set_dataframe(dataframe)
        self.view.resizeColumnsToContents()

        return self

    def dataframe(self):
        return self.model.dataframe()

    def clear(self):
        self.model.set_dataframe(pd.DataFrame())

        return self


class ConsoleTableManager(QtCore.QObject):
    tables_changed = QtCore.pyqtSignal()
    current_changed = QtCore.pyqtSignal(str)
    table_removed = QtCore.pyqtSignal(str, object)
    table_cleared = QtCore.pyqtSignal(str, object)

    def __init__(
        self,
        dock_area,
        default_name,
        default_table,
        default_dock,
        status_callback=None,
        active_callback=None,
    ):
        super().__init__(dock_area)
        self._dock_area = dock_area
        self._tables = {default_name: default_table}
        self._docks = {default_name: default_dock}
        self._default_name = default_name
        self._current_name = default_name
        self._status_callback = status_callback
        self._active_callback = active_callback

    def __repr__(self):
        return "ConsoleTableManager(current={self._current_name!r})"

    def __call__(self, data, name=None, *, activate=True):
        return self.show(data, name=name, activate=activate)

    @property
    def current(self):
        return self._tables[self._current_name]

    @property
    def current_name(self):
        return self._current_name

    def names(self):
        return list(self._tables)

    def get(self, name, *, activate=False):
        key = self._table_name(name)
        try:
            table = self._tables[key]
        except KeyError as e:
            raise KeyError(f"No console table named {key!r}") from e

        if activate:
            self._mark_active()
            self._set_current_name(key)
            self._raise_dock(self._docks[key])

        return table

    def new(self, name=None, *, activate=True):
        key = self._next_name() if name is None else self._table_name(name)
        if key in self._tables:
            return self.get(key, activate=activate)

        table = ConsoleTable()
        dock = Dock(key, size=(10, 6), closable=True)
        dock.addWidget(table.host)

        dock.activated.connect(lambda table_name=key: self.activate(table_name))
        dock.sigClosed.connect(self._forget_dock)

        self._dock_area.addDock(
            dock, position="above", relativeTo=self._docks[self._default_name]
        )
        self._tables[key] = table
        self._docks[key] = dock

        if activate:
            self._mark_active()
            self._set_current_name(key)
            dock.raiseDock()

        self.tables_changed.emit()

        return table

    def show(self, data, name=None, *, activate=True):
        table = self.current if name is None else self.new(name, activate=activate)
        if name is None and activate:
            self._mark_active()

        table.set_data(data)

        if self._status_callback is not None:
            self._status_callback(f"Updated table {self._current_name}")

        return table

    def rename(self, old_name, new_name):
        old_key = self._table_name(old_name)
        new_key = self._table_name(new_name)
        if old_key not in self._tables:
            raise KeyError(f"No console table named {old_key!r}")
        if new_key != old_key and new_key in self._tables:
            raise ValueError(f"Console table {new_key!r} alread exists")

        if new_key == old_key:
            self._set_current_name(new_key)
            return self._tables[new_key]

        self._mark_active()

        table = self._tables.pop(old_key)
        dock = self._docks.pop(old_key)
        self._tables[new_key] = table
        self._docks[new_key] = dock

        if old_key == self._default_name:
            self._default_name = new_key
        if old_key == self._current_name:
            self._current_name = new_key

        dock.setTitle(new_key)
        self.tables_changed.emit()
        self.current_changed.emit(self._current_name)

        return table

    def activate(self, name):
        key = self._table_name(name)
        if key not in self._tables:
            return

        self._set_current_name(key)
        self._mark_active()

    def close(self, name=None):
        key = self._current_name if name is None else self._table_name(name)
        if key == self._default_name:
            table = self._tables[key]
            table.clear()
            self.table_cleared.emit(key, table)
            self._set_current_name(key)
            return

        dock = self._docks.get(key)
        if dock is not None and dock.container() is not None:
            dock.close()
        else:
            self._forget(key)

    def clear(self):
        table = self.current
        table.clear()
        self.table_cleared.emit(self._current_name, table)

    def clear_all(self):
        for name, table in self._tables.items():
            table.clear()
            self.table_cleared.emit(name, table)

    def set_status_callback(self, callback):
        self._status_callback = callback

    def _forget_dock(self, dock):
        for name, known_dock in self._docks.items():
            if known_dock is dock:
                self._forget(name)
                return

    def _forget(self, name):
        if name == self._default_name:
            return
        if name not in self._tables:
            return

        table = self._tables.pop(name)
        self._docks.pop(name, None)

        if self._current_name == name:
            self._set_current_name(self._default_name)

        self.table_removed.emit(name, table)
        self.tables_changed.emit()

    def _raise_dock(self, dock):
        container = dock.container()
        raise_dock = getattr(container, "raiseDock", None)
        if raise_dock is not None:
            raise_dock(dock)

    def _set_current_name(self, key):
        if self._current_name == key:
            return

        self._current_name = key
        self.current_changed.emit(key)

    def _mark_active(self):
        if self._active_callback is not None:
            self._active_callback("table")

    def _next_name(self):
        index = 2
        while True:
            name = f"Table {index}"
            if name not in self._tables:
                return name
            index += 1

    def _table_name(self, name):
        key = str(name).strip()
        if not key:
            raise ValueError("Table name can't be empty")
        return key
