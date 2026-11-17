# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pathlib import Path

import numpy as np
import pandas as pd
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from ..ui.style import PANEL_SURFACE
from .docked_views import DockedViewManager


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

    raise ValueError("Table data must be scalar, 1D or 2D")


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
        if pd.api.types.is_scalar(value) and pd.isna(value):
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
        self.host.setObjectName("panelSurface")
        self.host.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.host.setStyleSheet(PANEL_SURFACE)
        self.layout = QtWidgets.QVBoxLayout(self.host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.view = QtWidgets.QTableView()
        self.view.setAlternatingRowColors(True)
        self.view.setSortingEnabled(False)
        self.view.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.view.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems
        )
        self.view.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.model = ConsoleTableModel(parent=self.view)
        self.view.setModel(self.model)

        self.layout.addWidget(self.view)

        self.copy_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence.StandardKey.Copy, self.view
        )
        self.copy_shortcut.activated.connect(self.copy_selection)

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

    def selected_text(self):
        indexes = self.view.selectedIndexes()
        if not indexes:
            return ""

        rows = sorted({idx.row() for idx in indexes})
        columns = sorted({idx.column() for idx in indexes})
        selected = {(idx.row(), idx.column()) for idx in indexes}

        lines = []
        for row in rows:
            values = []
            for column in columns:
                if (row, column) in selected:
                    model_index = self.model.index(row, column)
                    value = self.model.data(
                        model_index, QtCore.Qt.ItemDataRole.DisplayRole
                    )
                    values.append("" if value is None else str(value))
                else:
                    values.append("")
            lines.append("\t".join(values))

        return "\n".join(lines)

    def copy_selection(self):
        text = self.selected_text()
        if text:
            clipboard = QtWidgets.QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(text)

        return text

    def to_csv(self, path, *, index=True, **kwargs):
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        self.dataframe().to_csv(target, index=index, **kwargs)

        return target

    def clear(self):
        self.model.set_dataframe(pd.DataFrame())

        return self


class ConsoleTableManager(DockedViewManager):
    kind = "table"
    name_prefix = "Table"
    dock_prefix = "table"

    def __call__(self, data, name=None, *, activate=True):
        return self.show(data, name=name, activate=activate)

    def show(self, data, name=None, *, activate=True):
        table = self.current if name is None else self.new(name, activate=activate)
        if name is None and activate:
            self._docks[self._current_name].reveal()

        table.set_data(data)
        self.status_message.emit(f"Updated table {self._current_name}", False)

        return table

    def export(self, path, name=None, *, index=True, **kwargs):
        # use the actual table name so status message is accurate if activate=False
        table_name = self._current_name if name is None else self._key(name)
        table = self.current if name is None else self.get(table_name, activate=False)
        target = table.to_csv(path, index=index, **kwargs)

        self.status_message.emit(f"Exported table {table_name} to {target}", False)

        return target

    def _make_view(self):
        return ConsoleTable()
