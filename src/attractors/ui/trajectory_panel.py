from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

DEFAULT_PALETTE = [
    QtGui.QColor("#3b82f6"),
    QtGui.QColor("#f97316"),
    QtGui.QColor("#10b981"),
    QtGui.QColor("#ef4444"),
    QtGui.QColor("#8b5cf6"),
    QtGui.QColor("#06b6d4"),
    QtGui.QColor("#ec4899"),
    QtGui.QColor("#eab308"),
]

MAX_TRAJECTORIES = 8
ROW_TREE_MIN_HEIGHT = 96
ROW_HEIGHT = 26


class _TrajectoryRow(QtCore.QObject):
    changed = QtCore.pyqtSignal()
    style_changed = QtCore.pyqtSignal()
    remove_requested = QtCore.pyqtSignal(object)

    def __init__(
        self,
        ic: list[float],
        colour: QtGui.QColor,
        removeable: bool,
        *,
        label: str,
        n: int,
        t_max: int,
        parent=None,
    ):
        super().__init__(parent)
        children = [
            {"name": "Colour", "type": "color", "value": colour},
            {
                "name": "N",
                "type": "int",
                "value": n,
                "limits": (1000, 500000),
                "step": 1000,
            },
            {
                "name": "t_max",
                "type": "int",
                "value": t_max,
                "limits": (1, 750),
            },
            {
                "name": "x₀",
                "type": "float",
                "value": ic[0],
                "limits": (-1000.0, 1000.0),
                "step": 0.1,
            },
            {
                "name": "y₀",
                "type": "float",
                "value": ic[1],
                "limits": (-1000.0, 1000.0),
                "step": 0.1,
            },
            {
                "name": "z₀",
                "type": "float",
                "value": ic[2],
                "limits": (-1000.0, 1000.0),
                "step": 0.1,
            },
            {
                "name": "Alpha",
                "type": "slider",
                "value": 100,
                "limits": (0, 100),
            },
            {
                "name": "Size",
                "type": "float",
                "value": 1.0,
                "limits": (0.1, 20.0),
                "step": 0.1,
            },
            {
                "name": "Render",
                "type": "list",
                "limits": ["points", "line"],
                "value": "points",
            },
        ]
        if removeable:
            children.append({"name": "Remove", "type": "action"})

        self.param = Parameter.create(name=label, type="group", children=children)
        _remove_parameter_defaults(self.param)
        self.param.sigTreeStateChanged.connect(self._on_tree_change)
        remove_param = self.param.names.get("Remove")
        if remove_param is not None:
            remove_param.sigActivated.connect(
                lambda _param: self.remove_requested.emit(self)
            )

    def set_enabled(self, enabled: bool):
        for child in self.param.children():
            child.setOpts(enabled=enabled)

    def set_identity(self, index: int):
        label = f"T{index}"
        self.param.setName(label)

    def _on_tree_change(self, _param, changes):
        for param, change, _data in changes:
            if change != "value":
                continue
            if param.name() in {"Colour", "Alpha", "Size", "Render"}:
                self.style_changed.emit()
            else:
                self.changed.emit()

    def get_ic(self) -> list[float]:
        return [
            self.param.child("x₀").value(),
            self.param.child("y₀").value(),
            self.param.child("z₀").value(),
        ]

    def get_n(self) -> int:
        return self.param.child("N").value()

    def get_t_max(self) -> int:
        return self.param.child("t_max").value()

    def get_colour(self) -> QtGui.QColor:
        return self.param.child("Colour").value()

    def get_alpha(self) -> float:
        return self.param.child("Alpha").value() / 100.0

    def get_render_mode(self) -> str:
        return self.param.child("Render").value()

    def set_render_mode(self, mode: str):
        value = "line" if mode.lower() == "line" else "points"
        self.param.child("Render").setValue(value)

    def get_size(self):
        return self.param.child("Size").value()


class TrajectoryPanel(QtWidgets.QWidget):
    trajectories_changed = QtCore.pyqtSignal(list)
    styles_changed = QtCore.pyqtSignal(list)
    layout_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None, *, collapsible=True):
        super().__init__(parent)
        self._collapsible = collapsible
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        self.toggle_btn = None
        if self._collapsible:
            self.toggle_btn = QtWidgets.QPushButton("Trajectories ▸")
            self.toggle_btn.clicked.connect(self._toggle_content)
            layout.addWidget(self.toggle_btn)

        self._content = QtWidgets.QWidget()
        self._content.setObjectName("customPanelContent")
        self._content.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setContentsMargins(4, 6, 4, 6)
        content_layout.setSpacing(6)
        content_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        self._rows_container = ParameterTree(showHeader=True)
        self._rows_container.itemExpanded.connect(
            lambda _item: self._resize_to_content()
        )
        self._rows_container.itemCollapsed.connect(
            lambda _item: self._resize_to_content()
        )
        self._rows_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        self._rows_container.setMinimumHeight(ROW_TREE_MIN_HEIGHT)
        self._root_param = Parameter.create(
            name="Trajectories",
            type="group",
            children=[
                {
                    "name": "Enable multi-trajectory",
                    "type": "bool",
                    "value": False,
                },
                {"name": "Add trajectory", "type": "action"},
            ],
        )
        _remove_parameter_defaults(self._root_param)
        self._enable_param = self._root_param.child("Enable multi-trajectory")
        self._add_param = self._root_param.child("Add trajectory")
        self._enable_param.sigValueChanged.connect(
            lambda _param, value: self._on_enable_toggled(value)
        )
        self._add_param.sigActivated.connect(lambda _param: self._add_row())
        self._add_param.setOpts(enabled=False)
        self._rows_container.addParameters(self._root_param, showTop=False)

        self._rows: list[_TrajectoryRow] = []
        self._suppress_emit = False
        self._default_n = 1000
        self._default_t_max = 10

        content_layout.addWidget(self._rows_container)

        layout.addWidget(self._content)
        self._content.setVisible(not self._collapsible)

    def _toggle_content(self):
        if self.toggle_btn is None:
            return
        visible = not self._content.isVisible()
        self._content.setVisible(visible)
        self.toggle_btn.setText("Trajectories ▾" if visible else "Trajectories ▸")
        self.adjustSize()
        self.layout_changed.emit()

    def _on_enable_toggled(self, enabled: bool):
        self._add_param.setOpts(enabled=enabled)
        for row in self._rows:
            row.set_enabled(enabled)
        self._emit()

    def is_enabled(self) -> bool:
        return bool(self._enable_param.value())

    def reset(self, config):
        for row in self._rows:
            row.deleteLater()
            self._root_param.removeChild(row.param)
        self._rows.clear()
        self._default_n = int(config.time_defaults.n)
        self._default_t_max = int(config.time_defaults.t_max)
        self._add_row(
            ic=config.initial_conditions,
            removeable=False,
            n=self._default_n,
            t_max=self._default_t_max,
        )

    def _add_row(
        self,
        ic: list[float] | None = None,
        removeable: bool = True,
        *,
        n: int | None = None,
        t_max: int | None = None,
    ):
        if len(self._rows) >= MAX_TRAJECTORIES:
            return
        if ic is None:
            ic = self._rows[0].get_ic() if self._rows else [0.1, 0.0, 0.0]
        if n is None:
            n = self._rows[0].get_n() if self._rows else self._default_n
        if t_max is None:
            t_max = self._rows[0].get_t_max() if self._rows else self._default_t_max

        colour = DEFAULT_PALETTE[len(self._rows) % len(DEFAULT_PALETTE)]
        row = _TrajectoryRow(
            ic,
            colour,
            removeable,
            label=f"T{len(self._rows)}",
            n=n,
            t_max=t_max,
            parent=self,
        )
        row.changed.connect(self._emit)
        row.style_changed.connect(self._emit_styles)
        row.remove_requested.connect(self._remove_row)
        self._rows.append(row)
        insert_at = max(0, len(self._root_param.children()) - 1)
        self._root_param.insertChild(insert_at, row.param)
        row.set_enabled(self.is_enabled())
        self._sync_row_identities()
        self._resize_to_content()
        self._emit()

    def _remove_row(self, row: _TrajectoryRow):
        self._rows.remove(row)
        self._root_param.removeChild(row.param)
        row.deleteLater()
        self._sync_row_identities()
        self._resize_to_content()
        self._emit()

    def _sync_row_identities(self):
        for index, row in enumerate(self._rows):
            row.set_identity(index)

    def _resize_to_content(self):
        QtCore.QTimer.singleShot(0, self._apply_resize)

    def _apply_resize(self):
        max_item_bottom = 0
        item_count = 0
        for item in self._rows_container.listAllItems():
            rect = self._rows_container.visualItemRect(item)
            if rect.isValid():
                max_item_bottom = max(max_item_bottom, rect.y() + rect.height())
            item_count += 1
        if max_item_bottom:
            height = self._rows_container.header().height() + max_item_bottom + 6
        else:
            height = (
                self._rows_container.header().height() + item_count * ROW_HEIGHT + 6
            )
        self._rows_container.setFixedHeight(max(ROW_TREE_MIN_HEIGHT, height))
        self._content.adjustSize()
        self.adjustSize()
        self.layout_changed.emit()

    def _emit(self):
        if self._suppress_emit:
            return
        self.trajectories_changed.emit(self.get_trajectories())

    def _emit_styles(self):
        if self._suppress_emit:
            return
        self.styles_changed.emit(self.get_trajectories())

    def get_trajectories(self) -> list[dict]:
        if not self.is_enabled():
            return []
        return [
            {
                "label": f"T{index}",
                "ic": r.get_ic(),
                "n": r.get_n(),
                "t_max": r.get_t_max(),
                "colour": r.get_colour(),
                "alpha": r.get_alpha(),
                "size": r.get_size(),
                "render_mode": r.get_render_mode(),
            }
            for index, r in enumerate(self._rows)
        ]

    def set_render_mode_all(self, mode: str):
        self._suppress_emit = True
        try:
            for row in self._rows:
                row.set_render_mode(mode)
        finally:
            self._suppress_emit = False
        self._emit_styles()


def _remove_parameter_defaults(param):
    param.setDefault(None)
    for child in param.children():
        _remove_parameter_defaults(child)
