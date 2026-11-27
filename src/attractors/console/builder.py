# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from dataclasses import dataclass

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets


@dataclass(frozen=True)
class Kind:
    label: str
    view: str
    expressions: dict[str, str]
    ranges: dict[str, tuple[float, float]]
    samples: int


@dataclass
class SliderItem:
    name: str
    value: float = 1.0
    start: float = -10.0
    end: float = 10.0
    step: float = 0.01


@dataclass
class TraceItem:
    kind: str
    name: str
    expressions: dict[str, str]
    ranges: dict[str, tuple[float, float]]
    samples: int
    # colour or cmap name
    style: str


def item_key(item):
    return ("slider" if isinstance(item, SliderItem) else "trace", item.name)


class BuilderPanel(QtWidgets.QWidget):
    def __init__(self, console_panel, parent=None):
        super().__init__(parent)
        self._console_panel = console_panel
        self._explorer = None
        # build items per explorer and get key with item_key()
        self._items = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.target_label = QtWidgets.QLabel()
        layout.addWidget(self.target_label)

        buttons = QtWidgets.QHBoxLayout()
        self.add_button = QtWidgets.QToolButton()
        self.add_button.setText("Add")
        self.add_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.add_menu = QtWidgets.QMenu(self.add_button)
        self.add_menu.triggered.connect(lambda action: self.add(action.data()))
        self.add_button.setMenu(self.add_menu)
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_selected)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.item_list = QtWidgets.QListWidget()
        self.item_list.currentItemChanged.connect(self._load_selected)

        edit_host = QtWidgets.QWidget()
        edit_layout = QtWidgets.QVBoxLayout(edit_host)
        edit_layout.setContentsMargins(0, 4, 0, 0)

        self.editor = ItemEditor()
        self.editor.apply_requested.connect(self.apply_edit)
        edit_layout.addWidget(self.editor)

        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_edit)
        edit_layout.addWidget(self.apply_button)

        self.error_label = QtWidgets.QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        self.error_label.hide()
        edit_layout.addWidget(self.error_label)

        help_label = QtWidgets.QLabel(
            "Write expressions with +, -, *, /, ** and "
            f"{', '.join(FUNCTIONS)}. Constants: {', '.join(CONSTANTS)}. "
            "Any other name becomes a slider."
        )
        help_label.setWordWrap(True)
        help_label.setEnabled(False)
        edit_layout.addWidget(help_label)
        edit_layout.addStretch(1)

        edit_scroll = QtWidgets.QScrollArea()
        edit_scroll.setWidgetResizable(True)
        edit_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        edit_scroll.setWidget(edit_host)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.item_list)
        splitter.addWidget(edit_scroll)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        console_panel.active_view_changed.connect(self.sync)
        for manager in (console_panel.plots, console_panel.views3d):
            manager.current_changed.connect(lambda _name: self.sync())
            manager.views_changed.connect(self.sync)
            manager.view_removed.connect(
                lambda _name, view: self._items.pop(view.explore, None)
            )
