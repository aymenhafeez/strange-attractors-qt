# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import reprlib
from collections.abc import Sized
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
        # self.tree.header().setStretchLastSection(False)

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

            size, preview = self._describe(value)

            item = QtWidgets.QTreeWidgetItem(
                [name, type(value).__name__, size, preview]
            )
            self.tree.addTopLevelItem(item)

        self.tree.setSortingEnabled(True)

        # fit columns to contents on refresh so they can still be resized
        for column in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(column)

    @staticmethod
    def _describe(value):
        preview = reprlib.Repr(maxstring=80, maxother=80)

        if isinstance(value, np.ndarray):
            return str(value.shape), f"dtype={value.dtype}"

        if isinstance(value, (pd.DataFrame, pd.Series)):
            return str(value.shape), ""

        if isinstance(value, (str, bytes)):
            return str(len(value)), preview.repr(value)

        if isinstance(value, Sized):
            return str(len(value)), ""

        if type(value).__repr__ is object.__repr__:
            return "", ""

        # show numpy scalars as the actual value rather than of np.float(value)
        with np.printoptions(legacy="1.25"):
            preview = preview.repr(value)

        return "", "" if "\n" in preview else preview
