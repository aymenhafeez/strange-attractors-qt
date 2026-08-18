import numpy as np
import pandas as pd
from pyqtgraph.Qt import QtCore, QtWidgets
from scipy.sparse import data


def normalise_table_data(data):
    if isinstance(data, pd.DataFrame):
        return data.copy()

    if isinstance(data, pd.Series):
        name = data.name if data.name is not None else "value"
        return data.rename(name).to_frame()

    if isinstance(data, dict):
        return _noramlise_mapping(data)

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


def _noramlise_mapping(data):
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

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._dataframe)

    def columnCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
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
