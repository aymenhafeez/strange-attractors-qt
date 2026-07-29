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
SPIN_WIDTH = 60
ICON_BUTTON_SIZE = 20
IDENTITY_LABEL_WIDTH = 26
N_SPIN_WIDTH = 78
MODE_WIDTH = 52
FIELD_LABEL_WIDTH = 34


class _TrajectoryRow(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()
    style_changed = QtCore.pyqtSignal()
    remove_requested = QtCore.pyqtSignal(object)

    def __init__(
        self,
        ic: list[float],
        colour: QtGui.QColor,
        removeable: bool,
        *,
        n: int,
        t_max: int,
        parent=None,
    ):
        super().__init__(parent)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(8)

        meta_layout = QtWidgets.QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)
        outer.addLayout(meta_layout)

        self._colour = colour
        self.colour_btn = QtWidgets.QPushButton()
        self.colour_btn.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)
        self._apply_colour_btn()
        self.colour_btn.clicked.connect(self._pick_colour)
        meta_layout.addWidget(self.colour_btn)

        self.identity_label = QtWidgets.QLabel("T0")
        self.identity_label.setFixedWidth(IDENTITY_LABEL_WIDTH)
        self.identity_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.identity_label.setToolTip("Trajectory identity")
        self.identity_label.setStyleSheet("font-size: 11px; font-weight: 600;")
        meta_layout.addWidget(self.identity_label)

        n_label = QtWidgets.QLabel("N")
        n_label.setToolTip("Trajectory sample count")
        meta_layout.addWidget(n_label)
        self.n_spin = QtWidgets.QSpinBox()
        self.n_spin.setRange(1000, 500000)
        self.n_spin.setSingleStep(1000)
        self.n_spin.setValue(int(n))
        self.n_spin.setFixedWidth(N_SPIN_WIDTH)
        self.n_spin.setToolTip("Trajectory N")
        self.n_spin.valueChanged.connect(self.changed)
        meta_layout.addWidget(self.n_spin)

        t_max_label = QtWidgets.QLabel("t_max")
        t_max_label.setToolTip("Trajectory t_max")
        meta_layout.addWidget(t_max_label)
        self.t_max_spin = QtWidgets.QSpinBox()
        self.t_max_spin.setRange(1, 750)
        self.t_max_spin.setValue(int(t_max))
        self.t_max_spin.setFixedWidth(SPIN_WIDTH)
        self.t_max_spin.setToolTip("Trajectory t_max")
        self.t_max_spin.valueChanged.connect(self.changed)
        meta_layout.addWidget(self.t_max_spin)

        if removeable:
            remove_btn = QtWidgets.QToolButton()
            remove_btn.setText("×")
            remove_btn.setAutoRaise(True)
            remove_btn.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)
            remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
            meta_layout.addWidget(remove_btn)
        else:
            meta_layout.addSpacing(ICON_BUTTON_SIZE + 4)

        ic_label = QtWidgets.QLabel("Initial conditions")
        ic_label.setStyleSheet("font-size: 11px; font-weight: 600;")
        outer.addWidget(ic_label)

        ic_layout = QtWidgets.QHBoxLayout()
        ic_layout.setContentsMargins(0, 0, 0, 0)
        ic_layout.setSpacing(6)
        self.spins: list[QtWidgets.QDoubleSpinBox] = []
        for axis, val in zip(("x₀", "y₀", "z₀"), ic):
            lbl = QtWidgets.QLabel(axis)
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-1000.0, 1000.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setValue(val)
            spin.setFixedWidth(SPIN_WIDTH)
            spin.setFixedHeight(28)
            spin.setToolTip(f"{axis} initial condition")
            spin.valueChanged.connect(self.changed)
            ic_layout.addWidget(lbl)
            ic_layout.addWidget(spin)
            self.spins.append(spin)
        ic_layout.addStretch(1)
        outer.addLayout(ic_layout)

        alpha_row = QtWidgets.QHBoxLayout()
        alpha_row.setContentsMargins(0, 0, 0, 0)
        alpha_row.setSpacing(6)
        alpha_label = QtWidgets.QLabel("α")
        alpha_label.setFixedWidth(FIELD_LABEL_WIDTH)
        alpha_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        alpha_row.addWidget(alpha_label)
        self.alpha_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.alpha_slider.setRange(0, 100)
        self.alpha_slider.setValue(100)
        self.alpha_slider.setFixedHeight(18)
        self.alpha_slider.valueChanged.connect(self.style_changed)
        alpha_row.addWidget(self.alpha_slider)
        self.line_check = QtWidgets.QCheckBox("Line")
        self.line_check.setFixedWidth(MODE_WIDTH)
        self.line_check.setToolTip("Render this trajectory as a line")
        self.line_check.toggled.connect(self.style_changed)
        alpha_row.addWidget(self.line_check)
        outer.addLayout(alpha_row)

    def _apply_colour_btn(self):
        self.colour_btn.setStyleSheet(
            f"background-color: {self._colour.name()}; border: 1px solid #555;"
        )

    def set_identity(self, index: int):
        label = f"T{index}"
        self.identity_label.setText(label)
        tooltip = f"{label} colour"
        self.colour_btn.setToolTip(tooltip)
        self.identity_label.setToolTip(f"{label} trajectory")

    def _pick_colour(self):
        colour = QtWidgets.QColorDialog.getColor(self._colour, self)
        if colour.isValid():
            self._colour = colour
            self._apply_colour_btn()
            self.style_changed.emit()

    def get_ic(self) -> list[float]:
        return [s.value() for s in self.spins]

    def get_n(self) -> int:
        return self.n_spin.value()

    def get_t_max(self) -> int:
        return self.t_max_spin.value()

    def get_colour(self) -> QtGui.QColor:
        return self._colour

    def get_alpha(self) -> float:
        return self.alpha_slider.value() / 100.0

    def get_render_mode(self) -> str:
        return "line" if self.line_check.isChecked() else "points"

    def set_ic(self, ic: list[float]):
        for spin, val in zip(self.spins, ic):
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)

    def set_time(self, *, n: int, t_max: int):
        self.n_spin.blockSignals(True)
        self.t_max_spin.blockSignals(True)
        self.n_spin.setValue(int(n))
        self.t_max_spin.setValue(int(t_max))
        self.n_spin.blockSignals(False)
        self.t_max_spin.blockSignals(False)

    def set_colour(self, colour: QtGui.QColor):
        if colour.isValid():
            self._colour = colour
            self._apply_colour_btn()

    def set_alpha(self, alpha: float):
        value = max(0, min(100, round(float(alpha) * 100)))
        self.alpha_slider.blockSignals(True)
        self.alpha_slider.setValue(value)
        self.alpha_slider.blockSignals(False)

    def set_render_mode(self, mode: str):
        checked = str(mode).lower() == "line"
        self.line_check.blockSignals(True)
        self.line_check.setChecked(checked)
        self.line_check.blockSignals(False)


class TrajectoryPanel(QtWidgets.QWidget):
    trajectories_changed = QtCore.pyqtSignal(list)
    styles_changed = QtCore.pyqtSignal(list)

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
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)
        content_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

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
        rows_container_layout.setSpacing(6)
        rows_container_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        self._rows_layout = QtWidgets.QVBoxLayout()
        self._rows_layout.setSpacing(8)
        self._rows_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        rows_container_layout.addLayout(self._rows_layout)

        self._rows: list[_TrajectoryRow] = []
        self._suppress_emit = False
        self._default_n = 1000
        self._default_t_max = 10

        content_layout.addWidget(self._rows_container)

        self._add_btn = QtWidgets.QPushButton("+ Add")
        self._add_btn.setFixedHeight(30)
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(lambda: self._add_row())
        content_layout.addWidget(self._add_btn)
        layout.addWidget(self._content)
        self._content.setVisible(not self._collapsible)

    def _toggle_content(self):
        if self.toggle_btn is None:
            return
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
        row = _TrajectoryRow(ic, colour, removeable, n=n, t_max=t_max)
        row.changed.connect(self._emit)
        row.style_changed.connect(self._emit_styles)
        row.remove_requested.connect(self._remove_row)
        self._rows_layout.addWidget(row)
        self._rows.append(row)
        self._sync_row_identities()
        self._resize_to_content()
        self._emit()

    def _remove_row(self, row: _TrajectoryRow):
        self._rows_layout.removeWidget(row)
        self._rows.remove(row)
        row.hide()
        row.setParent(None)
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
            {
                "label": f"T{index}",
                "ic": r.get_ic(),
                "n": r.get_n(),
                "t_max": r.get_t_max(),
                "colour": r.get_colour(),
                "alpha": r.get_alpha(),
                "render_mode": r.get_render_mode(),
            }
            for index, r in enumerate(self._rows)
        ]

    def get_session_state(self) -> dict:
        return {
            "enabled": self._enable_check.isChecked(),
            "rows": [
                {
                    "ic": [float(v) for v in row.get_ic()],
                    "n": int(row.get_n()),
                    "t_max": int(row.get_t_max()),
                    "colour": row.get_colour().name(),
                    "alpha": float(row.get_alpha()),
                    "render_mode": row.get_render_mode(),
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
                row_data = row_state if isinstance(row_state, dict) else {}
                n = _positive_int_from_session_row(row_data, "n", self._default_n)
                t_max = _positive_int_from_session_row(
                    row_data,
                    "t_max",
                    self._default_t_max,
                )
                self._add_row(ic=ic, removeable=idx > 0, n=n, t_max=t_max)
                row = self._rows[-1]

                colour = QtGui.QColor(str(row_data.get("colour", "")))
                row.set_colour(colour)
                try:
                    row.set_alpha(float(row_data.get("alpha", 1.0)))
                except (TypeError, ValueError):
                    row.set_alpha(1.0)
                row.set_render_mode(row_data.get("render_mode", "points"))

            enabled = bool(state.get("enabled", False))

            with QtCore.QSignalBlocker(self._enable_check):
                self._enable_check.setChecked(enabled)
            self._rows_container.setEnabled(enabled)
            self._add_btn.setEnabled(enabled)

        finally:
            self._suppress_emit = False

        self._resize_to_content()
        self._emit()

    def set_render_mode_all(self, mode: str):
        self._suppress_emit = True
        try:
            for row in self._rows:
                row.set_render_mode(mode)
        finally:
            self._suppress_emit = False
        self._emit_styles()


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


def _positive_int_from_session_row(row_state, key, fallback):
    try:
        value = int(row_state.get(key, fallback))
    except (AttributeError, TypeError, ValueError):
        return int(fallback)

    if value <= 0:
        return int(fallback)

    return value
