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
SPIN_WIDTH = 64
ICON_BUTTON_SIZE = 20


class _TrajectoryRow(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()
    style_changed = QtCore.pyqtSignal()
    remove_requested = QtCore.pyqtSignal(object)

    def __init__(
        self, ic: list[float], colour: QtGui.QColor, removeable: bool, parent=None
    ):
        super().__init__(parent)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(8)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        outer.addLayout(layout)

        self._colour = colour
        self.colour_btn = QtWidgets.QPushButton()
        self.colour_btn.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)
        self._apply_colour_btn()
        self.colour_btn.clicked.connect(self._pick_colour)
        layout.addWidget(self.colour_btn)

        self.spins: list[QtWidgets.QDoubleSpinBox] = []
        for val in ic:
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-1000.0, 1000.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setValue(val)
            spin.setFixedWidth(SPIN_WIDTH)
            spin.setFixedHeight(28)
            spin.valueChanged.connect(self.changed)
            layout.addWidget(spin)
            self.spins.append(spin)

        if removeable:
            remove_btn = QtWidgets.QToolButton()
            remove_btn.setText("×")
            remove_btn.setAutoRaise(True)
            remove_btn.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)
            remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
            layout.addWidget(remove_btn)
        else:
            layout.addSpacing(ICON_BUTTON_SIZE + 4)

        alpha_row = QtWidgets.QHBoxLayout()
        alpha_row.setContentsMargins(0, 0, 0, 0)
        alpha_row.setSpacing(6)
        alpha_row.addSpacing(ICON_BUTTON_SIZE + 6)
        alpha_label = QtWidgets.QLabel("α")
        alpha_row.addWidget(alpha_label)
        self.alpha_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.alpha_slider.setRange(0, 100)
        self.alpha_slider.setValue(100)
        self.alpha_slider.setFixedHeight(18)
        self.alpha_slider.valueChanged.connect(self.style_changed)
        alpha_row.addWidget(self.alpha_slider)
        alpha_row.addSpacing(ICON_BUTTON_SIZE + 4)
        outer.addLayout(alpha_row)

    def _apply_colour_btn(self):
        self.colour_btn.setStyleSheet(
            f"background-color: {self._colour.name()}; border: 1px solid #555;"
        )

    def _pick_colour(self):
        colour = QtWidgets.QColorDialog.getColor(self._colour, self)
        if colour.isValid():
            self._colour = colour
            self._apply_colour_btn()
            self.style_changed.emit()

    def get_ic(self) -> list[float]:
        return [s.value() for s in self.spins]

    def get_colour(self) -> QtGui.QColor:
        return self._colour

    def get_alpha(self) -> float:
        return self.alpha_slider.value() / 100.0

    def set_ic(self, ic: list[float]):
        for spin, val in zip(self.spins, ic):
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)

    def set_colour(self, colour: QtGui.QColor):
        if colour.isValid():
            self._colour = colour
            self._apply_colour_btn()

    def set_alpha(self, alpha: float):
        value = max(0, min(100, round(float(alpha) * 100)))
        self.alpha_slider.blockSignals(True)
        self.alpha_slider.setValue(value)
        self.alpha_slider.blockSignals(False)


class TrajectoryPanel(QtWidgets.QWidget):
    trajectories_changed = QtCore.pyqtSignal(list)
    styles_changed = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.toggle_btn = QtWidgets.QPushButton("Trajectories ▸")
        self.toggle_btn.clicked.connect(self._toggle_content)
        layout.addWidget(self.toggle_btn)

        self._content = QtWidgets.QWidget()
        self._content.setObjectName("customPanelContent")
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        enable_row = QtWidgets.QHBoxLayout()
        self._enable_check = QtWidgets.QCheckBox("Enable multi-trajectory")
        self._enable_check.setChecked(False)
        self._enable_check.toggled.connect(self._on_enable_toggled)
        enable_row.addWidget(self._enable_check)
        content_layout.addLayout(enable_row)

        self._rows_container = QtWidgets.QWidget()
        self._rows_container.setObjectName("rowsContainer")
        self._rows_container.setEnabled(False)
        rows_container_layout = QtWidgets.QVBoxLayout(self._rows_container)
        rows_container_layout.setContentsMargins(0, 0, 0, 0)
        rows_container_layout.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        header.addSpacing(ICON_BUTTON_SIZE + 4)
        for axis in ("x₀", "y₀", "z₀"):
            lbl = QtWidgets.QLabel(axis)
            lbl.setFixedWidth(SPIN_WIDTH)
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            header.addWidget(lbl)
        rows_container_layout.addLayout(header)

        self._rows_layout = QtWidgets.QVBoxLayout()
        self._rows_layout.setSpacing(16)
        rows_container_layout.addLayout(self._rows_layout)

        self._rows: list[_TrajectoryRow] = []
        self._suppress_emit = False

        content_layout.addWidget(self._rows_container)

        self._add_btn = QtWidgets.QPushButton("+ Add")
        self._add_btn.setFixedHeight(30)
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(lambda: self._add_row())
        content_layout.addWidget(self._add_btn)
        layout.addWidget(self._content)
        self._content.setVisible(False)

    def _toggle_content(self):
        visible = not self._content.isVisible()
        self._content.setVisible(visible)
        self.toggle_btn.setText("Trajectories ▾" if visible else "Trajectories ▸")
        self.adjustSize()

    def _on_enable_toggled(self, enabled: bool):
        self._rows_container.setEnabled(enabled)
        self._add_btn.setEnabled(enabled)
        self._emit()

    def is_enabled(self) -> bool:
        return self._enable_check.isChecked()

    def reset(self, config):
        for row in self._rows:
            self._rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._add_row(ic=config.initial_conditions, removeable=False)

    def _add_row(self, ic: list[float] | None = None, removeable: bool = True):
        if len(self._rows) >= MAX_TRAJECTORIES:
            return
        if ic is None:
            ic = self._rows[0].get_ic() if self._rows else [0.1, 0.0, 0.0]

        colour = DEFAULT_PALETTE[len(self._rows) % len(DEFAULT_PALETTE)]
        row = _TrajectoryRow(ic, colour, removeable)
        row.changed.connect(self._emit)
        row.style_changed.connect(self._emit_styles)
        row.remove_requested.connect(self._remove_row)
        self._rows_layout.addWidget(row)
        self._rows.append(row)
        self._resize_to_content()
        self._emit()

    def _remove_row(self, row: _TrajectoryRow):
        self._rows_layout.removeWidget(row)
        self._rows.remove(row)
        row.hide()
        row.setParent(None)
        row.deleteLater()
        self._resize_to_content()
        self._emit()

    def _resize_to_content(self):
        QtCore.QTimer.singleShot(0, self._apply_resize)

    def _apply_resize(self):
        self._content.adjustSize()
        self.adjustSize()

    def _emit(self):
        if self._suppress_emit:
            return
        self.trajectories_changed.emit(self.get_trajectories())

    def _emit_styles(self):
        if self._suppress_emit:
            return
        self.styles_changed.emit(self.get_trajectories())

    def get_trajectories(self) -> list[dict]:
        if not self._enable_check.isChecked():
            return []
        return [
            {"ic": r.get_ic(), "colour": r.get_colour(), "alpha": r.get_alpha()}
            for r in self._rows
        ]

    def get_session_state(self) -> dict:
        return {
            "enabled": self._enable_check.isChecked(),
            "rows": [
                {
                    "ic": [float(v) for v in row.get_ic()],
                    "colour": row.get_colour().name(),
                    "alpha": float(row.get_alpha()),
                }
                for row in self._rows
            ],
        }

    def set_session_state(self, state, config):
        if not isinstance(state, dict):
            return

        rows = state.get("rows")
        if not isinstance(rows, list) or not rows:
            return

        self._suppress_emit = True
        try:
            for row in self._rows:
                self._rows_layout.removeWidget(row)
                row.deleteLater()
            self._rows.clear()

            for idx, row_state in enumerate(rows[:MAX_TRAJECTORIES]):
                ic = _ic_from_session_row(row_state, config.initial_conditions)
                self._add_row(ic=ic, removeable=idx > 0)
                row = self._rows[-1]
                row_data = row_state if isinstance(row_state, dict) else {}

                colour = QtGui.QColor(str(row_data.get("colour", "")))
                row.set_colour(colour)
                try:
                    row.set_alpha(float(row_data.get("alpha", 1.0)))
                except (TypeError, ValueError):
                    row.set_alpha(1.0)

            enabled = bool(state.get("enabled", False))
            with QtCore.QSignalBlocker(self._enable_check):
                self._enable_check.setChecked(enabled)
            self._rows_container.setEnabled(enabled)
            self._add_btn.setEnabled(enabled)
        finally:
            self._suppress_emit = False

        self._resize_to_content()
        self._emit()


def _ic_from_session_row(row_state, fallback):
    if not isinstance(row_state, dict):
        return list(fallback)

    raw_ic = row_state.get("ic")
    if not isinstance(raw_ic, list) or len(raw_ic) != 3:
        return list(fallback)

    try:
        return [float(v) for v in raw_ic]
    except (TypeError, ValueError):
        return list(fallback)
