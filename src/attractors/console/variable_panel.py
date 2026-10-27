# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from types import BuiltinFunctionType, FunctionType, ModuleType

import numpy as np
import pandas as pd
from pyqtgraph.Qt import QtCore, QtWidgets


class VariablePanel(QtWidgets.QWidget):
    refresh_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # toolbar = QtWidgets.QToolBar(self)
        # toolbar.setMovable(False)
        # refresh = toolbar.addAction("Refresh")
        # refresh.triggered.connect(lambda: self.refresh_requested.emit())

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type", "Shape / size", "Value"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tree.setSortingEnabled(True)
        self.tree.sortItems(0, QtCore.Qt.SortOrder.AscendingOrder)

        # layout.addWidget(toolbar)
        layout.addWidget(self.tree)

    def set_namespace(self, namespace, defaults):
        self.tree.setSortingEnabled(False)
        self.tree.clear()

        for name, value in list(namespace.items()):
            if not isinstance(name, str) or name.startswith("_"):
                continue
            if name in {"In", "Out", "get_ipython", "exit", "quit"}:
                continue
            if name in defaults and value is defaults[name]:
                continue
            if isinstance(value, (ModuleType, FunctionType, BuiltinFunctionType, type)):
                continue

            try:
                size, preview = self._describe(value)
            except Exception:  # noqa: BLE001 - Keep preview errors out of the console.
                size, preview = "", "<preview unavailable>"

            item = QtWidgets.QTreeWidgetItem(
                [name, type(value).__name__, size, preview]
            )
            self.tree.addTopLevelItem(item)

        self.tree.setSortingEnabled(True)

    @staticmethod
    def _describe(value):
        if isinstance(value, np.ndarray):
            return str(value.shape), f"dtype={value.dtype}"
        if isinstance(value, (pd.DataFrame, pd.Series)):
            return str(value.shape), ""
        if type(value) in (str, bytes):
            preview = repr(value[:80])
            if len(value) > 80:
                preview += "..."
            return str(len(value)), preview
        if type(value) in (list, tuple, dict, set, frozenset):
            return str(len(value)), ""
        if value is None or type(value) in (bool, int, float, complex):
            return "", repr(value)[:120]
        if isinstance(value, (np.number, np.bool_)):
            return "", repr(value)[:120]

        return "", ""
