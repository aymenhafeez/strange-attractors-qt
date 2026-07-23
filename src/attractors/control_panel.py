from functools import partial

from pyqtgraph.Qt import QtCore, QtWidgets

from .custom_panel import CustomPanel
from .registry import ATTRACTORS
from .trajectory_panel import TrajectoryPanel

STEP = 1000


def _slider_index(value, min_val, step):
    return int(round((value - min_val) / step))


def _slider_value(index, min_val, step):
    return min_val + index * step


class ControlPanel(QtWidgets.QWidget):
    attractor_changed = QtCore.pyqtSignal(str)
    solve_requested = QtCore.pyqtSignal(bool)
    projections_requested = QtCore.pyqtSignal()
    bifurcation_requested = QtCore.pyqtSignal()
    poincare_requested = QtCore.pyqtSignal()
    n_changed = QtCore.pyqtSignal(int)
    t_max_changed = QtCore.pyqtSignal(int)
    animation_toggled = QtCore.pyqtSignal()
    animation_speed_changed = QtCore.pyqtSignal(int)
    camera_reset_requested = QtCore.pyqtSignal()
    camera_fit_requested = QtCore.pyqtSignal()
    save_requested = QtCore.pyqtSignal()
    preset_save_requested = QtCore.pyqtSignal(str)
    preset_load_requested = QtCore.pyqtSignal(str)
    preset_delete_requested = QtCore.pyqtSignal(str)
    traj_tail_length_changed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("controlPanel")

        # plain QWidget to work around objectName selector bug on QWidget subclasses
        inner = QtWidgets.QWidget()
        inner.setObjectName("controlPanel")

        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(inner)

        self.panel_layout = QtWidgets.QVBoxLayout(inner)
        self.panel_layout.setContentsMargins(8, 8, 8, 8)
        self.panel_layout.setSpacing(7)

        self.current_name = list(ATTRACTORS.keys())[0]
        self.slider_rows = []
        self.n_slider_row = None
        self.n_slider_wrapper = None
        self.t_max_slider_row = None
        self.t_max_slider_wrapper = None

        options = QtWidgets.QHBoxLayout()

        self.dropdown = QtWidgets.QPushButton(list(ATTRACTORS.keys())[0])
        menu = QtWidgets.QMenu(self.dropdown)
        for name in ATTRACTORS:
            action = menu.addAction(name)
            assert action is not None
            action.triggered.connect(partial(self._on_attractor_selected, name))
        custom_action = menu.addAction("Custom")
        assert custom_action is not None
        custom_action.triggered.connect(partial(self._on_attractor_selected, "Custom"))
        self.dropdown.setMenu(menu)

        self.tools_button = QtWidgets.QPushButton("Tools")
        tools_menu = QtWidgets.QMenu(self.tools_button)
        projections_action = tools_menu.addAction("Projection heatmaps")
        projections_action.triggered.connect(self.projections_requested)
        bifurcation_action = tools_menu.addAction("Bifurcation diagram")
        bifurcation_action.triggered.connect(self.bifurcation_requested)
        poincare_action = tools_menu.addAction("Poincaré section")
        poincare_action.triggered.connect(self.poincare_requested)
        self.tools_button.setMenu(tools_menu)

        options.addWidget(self.dropdown)
        options.addWidget(self.tools_button)
        self.panel_layout.addLayout(options)

        self.controls_scroll = QtWidgets.QScrollArea()
        self.controls_scroll.setWidgetResizable(True)
        self.controls_tab = QtWidgets.QWidget()
        self.controls_layout = QtWidgets.QVBoxLayout(self.controls_tab)
        self.controls_layout.setContentsMargins(8, 8, 8, 8)
        self.controls_layout.setSpacing(7)
        self.controls_scroll.setWidget(self.controls_tab)
        self.panel_layout.addWidget(self.controls_scroll)

        options_row = QtWidgets.QHBoxLayout()

        self.anim_button = QtWidgets.QPushButton("▶ Play")
        self.anim_button.clicked.connect(self.animation_toggled)

        self.point_button = QtWidgets.QCheckBox("Point")
        self.point_button.setChecked(True)

        options_row.addWidget(self.anim_button)
        options_row.addWidget(self.point_button)
        options_row.addStretch(1)

        self.line_mode = QtWidgets.QCheckBox("Line")
        self.line_mode.setChecked(False)
        options_row.addWidget(self.line_mode)

        self.trail_mode = QtWidgets.QCheckBox("Trail")
        self.trail_mode.setChecked(False)
        options_row.addWidget(self.trail_mode)

        self.show_grid = QtWidgets.QCheckBox("Grid")
        self.show_grid.setChecked(True)
        options_row.addWidget(self.show_grid)

        self.controls_layout.addLayout(options_row)

        alpha_row = QtWidgets.QHBoxLayout()
        alpha_row.setSpacing(10)
        alpha_label = QtWidgets.QLabel("α ")
        self.alpha_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.alpha_slider.setRange(0, 100)
        self.alpha_slider.setValue(100)
        self.alpha_spin = QtWidgets.QSpinBox()
        self.alpha_spin.setKeyboardTracking(False)
        self.alpha_spin.setRange(0, 100)
        self.alpha_spin.setValue(100)
        self.alpha_slider.valueChanged.connect(self.alpha_spin.setValue)
        self.alpha_spin.valueChanged.connect(self.alpha_slider.setValue)
        alpha_row.addWidget(alpha_label)
        alpha_row.addWidget(self.alpha_slider)
        alpha_row.addWidget(self.alpha_spin)
        alpha_wrapper = QtWidgets.QWidget()
        alpha_wrapper.setLayout(alpha_row)
        self.controls_layout.addWidget(alpha_wrapper)

        speed_row = QtWidgets.QHBoxLayout()
        speed_row.setSpacing(10)
        speed_label = QtWidgets.QLabel("Speed")
        self.anim_speed_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.anim_speed_slider.setRange(1, 500)
        self.anim_speed_slider.setValue(100)
        self.anim_speed_spin = QtWidgets.QSpinBox()
        self.anim_speed_spin.setKeyboardTracking(False)
        self.anim_speed_spin.setRange(1, 500)
        self.anim_speed_spin.setValue(100)
        self.anim_speed_slider.valueChanged.connect(self.anim_speed_spin.setValue)
        self.anim_speed_spin.valueChanged.connect(self.anim_speed_slider.setValue)
        self.anim_speed_spin.valueChanged.connect(self.animation_speed_changed.emit)
        speed_row.addWidget(speed_label)
        speed_row.addWidget(self.anim_speed_slider)
        speed_row.addWidget(self.anim_speed_spin)
        speed_wrapper = QtWidgets.QWidget()
        speed_wrapper.setLayout(speed_row)
        self.controls_layout.addWidget(speed_wrapper)

        traj_tail_row = QtWidgets.QHBoxLayout()
        traj_tail_row.setSpacing(10)
        traj_tail_label = QtWidgets.QLabel("Len")
        self.traj_tail_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.traj_tail_slider.setRange(1, 500)
        self.traj_tail_slider.setValue(5)
        self.traj_tail_spin = QtWidgets.QSpinBox()
        self.traj_tail_spin.setKeyboardTracking(False)
        self.traj_tail_spin.setRange(1000, 500000)
        self.traj_tail_spin.setSingleStep(STEP)
        self.traj_tail_spin.setValue(5000)
        self.traj_tail_slider.param_step = STEP
        self.traj_tail_spin.param_step = STEP
        self.traj_tail_slider.valueChanged.connect(
            lambda val: self.traj_tail_spin.setValue(
                val * self.traj_tail_slider.param_step
            )
        )
        self.traj_tail_spin.valueChanged.connect(
            lambda val: self.traj_tail_slider.setValue(
                int(val / self.traj_tail_spin.param_step)
            )
        )
        self.traj_tail_spin.valueChanged.connect(self.traj_tail_length_changed.emit)
        traj_tail_row.addWidget(traj_tail_label)
        traj_tail_row.addWidget(self.traj_tail_slider)
        traj_tail_row.addWidget(self.traj_tail_spin)
        traj_tail_wrapper = QtWidgets.QWidget()
        traj_tail_wrapper.setLayout(traj_tail_row)
        traj_tail_wrapper.setVisible(False)
        self.trail_mode.toggled.connect(traj_tail_wrapper.setVisible)
        self.controls_layout.addWidget(traj_tail_wrapper)

        self.controls_grid = QtWidgets.QGridLayout()
        self.controls_grid.setSpacing(6)
        self.reset_button = QtWidgets.QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_to_defaults)
        self.reset_camera_button = QtWidgets.QPushButton("Reset camera")
        self.reset_camera_button.clicked.connect(self.camera_reset_requested.emit)
        self.fit_camera_button = QtWidgets.QPushButton("Fit view")
        self.fit_camera_button.clicked.connect(self.camera_fit_requested.emit)
        self.save_button = QtWidgets.QPushButton("Save view")
        self.save_button.clicked.connect(self.save_requested.emit)
        self.controls_grid.addWidget(self.reset_button, 0, 0)
        self.controls_grid.addWidget(self.reset_camera_button, 0, 1)
        self.controls_grid.addWidget(self.fit_camera_button, 1, 0)
        self.controls_grid.addWidget(self.save_button, 1, 1)

        self.preset_toggle_btn = QtWidgets.QPushButton("Presets ▸")
        self.preset_toggle_btn.clicked.connect(self._toggle_preset_content)

        self.preset_content = QtWidgets.QWidget()
        self.preset_content.setObjectName("customPanelContent")

        self.preset_label = QtWidgets.QLabel("Preset library")
        self.preset_name_edit = QtWidgets.QLineEdit()
        self.preset_name_edit.setPlaceholderText("Preset name")
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.currentTextChanged.connect(self._on_preset_selected)
        self.save_preset_button = QtWidgets.QPushButton("Save")
        self.save_preset_button.clicked.connect(self._emit_preset_save)
        self.load_preset_button = QtWidgets.QPushButton("Load")
        self.load_preset_button.clicked.connect(self._emit_preset_load)
        self.delete_preset_button = QtWidgets.QPushButton("Delete")
        self.delete_preset_button.clicked.connect(self._emit_preset_delete)

        self.preset_grid = QtWidgets.QGridLayout()
        self.preset_grid.setContentsMargins(6, 6, 6, 4)
        self.preset_grid.setSpacing(6)
        self.preset_grid.addWidget(self.preset_label, 0, 0, 1, 2)
        self.preset_grid.addWidget(self.preset_name_edit, 1, 0, 1, 2)
        self.preset_grid.addWidget(self.preset_combo, 2, 0, 1, 2)
        self.preset_grid.addWidget(self.save_preset_button, 3, 0)
        self.preset_grid.addWidget(self.load_preset_button, 3, 1)
        self.preset_grid.addWidget(self.delete_preset_button, 4, 0, 1, 2)
        self.preset_content.setLayout(self.preset_grid)
        self.preset_content.setVisible(False)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(28)
        self.status_label.setStyleSheet("color: transparent; font-size: 11px;")

        self.trajectory_panel = TrajectoryPanel()
        self.custom_panel = CustomPanel()
        self.custom_panel.setVisible(False)

        self.controls_layout.addLayout(self.controls_grid)
        self.controls_layout.addWidget(self.preset_toggle_btn)
        self.controls_layout.addWidget(self.preset_content)
        self.controls_layout.addWidget(self.status_label)

    def _on_attractor_selected(self, name):
        self.set_current_attractor(name)
        self.attractor_changed.emit(name)

    def set_current_attractor(self, name):
        self.current_name = name
        self.dropdown.setText(name)
        self.custom_panel.setVisible(name == "Custom")

    def set_saved_presets(self, names, selected=None):
        selected_name = selected or self.current_preset_name()
        with QtCore.QSignalBlocker(self.preset_combo):
            self.preset_combo.clear()
            self.preset_combo.addItems(names)
            if selected_name in names:
                self.preset_combo.setCurrentText(selected_name)

        has_presets = self.preset_combo.count() > 0
        self.load_preset_button.setEnabled(has_presets)
        self.delete_preset_button.setEnabled(has_presets)
        self._on_preset_selected(self.preset_combo.currentText())

    def current_preset_name(self):
        return self.preset_combo.currentText().strip()

    def _preset_name_from_edit_or_combo(self):
        return self.preset_name_edit.text().strip() or self.current_preset_name()

    def _on_preset_selected(self, name):
        with QtCore.QSignalBlocker(self.preset_name_edit):
            self.preset_name_edit.setText(name)

    def _toggle_preset_content(self):
        visible = self.preset_content.isHidden()
        self.preset_content.setVisible(visible)
        self.preset_toggle_btn.setText("Presets ▾" if visible else "Presets ▸")

    def _emit_preset_save(self):
        self.preset_save_requested.emit(self._preset_name_from_edit_or_combo())

    def _emit_preset_load(self):
        self.preset_load_requested.emit(self.current_preset_name())

    def _emit_preset_delete(self):
        self.preset_delete_requested.emit(self.current_preset_name())

    def set_anim_playing(self, playing):
        self.anim_button.setText("■ Stop" if playing else "▶ Play")

    def configure(self, config):
        self._clear_sliders()
        self._build_n_slider(config)
        self._build_t_max_slider(config)
        self._build_param_sliders(config)
        self.controls_layout.addWidget(self.trajectory_panel)
        self.controls_layout.addWidget(self.custom_panel)
        self.controls_layout.addStretch()

    def _clear_sliders(self):
        if self.n_slider_wrapper is not None:
            self.controls_layout.removeWidget(self.n_slider_wrapper)
            self.n_slider_wrapper.deleteLater()
            self.n_slider_row = None
            self.n_slider_wrapper = None
        if self.t_max_slider_wrapper is not None:
            self.controls_layout.removeWidget(self.t_max_slider_wrapper)
            self.t_max_slider_wrapper.deleteLater()
            self.t_max_slider_row = None
            self.t_max_slider_wrapper = None
        for *_, wrapper in self.slider_rows:
            self.controls_layout.removeWidget(wrapper)
            wrapper.deleteLater()
        self.slider_rows.clear()
        self.controls_layout.removeWidget(self.trajectory_panel)
        self.controls_layout.removeWidget(self.custom_panel)
        while self.controls_layout.count():
            item = self.controls_layout.itemAt(self.controls_layout.count() - 1)
            if item is not None and item.spacerItem():
                self.controls_layout.takeAt(self.controls_layout.count() - 1)
            else:
                break

    def _build_n_slider(self, config):
        n_row = QtWidgets.QHBoxLayout()
        self.n_slider_row = n_row
        n_label = QtWidgets.QLabel("N")
        n_row.addWidget(n_label)
        n_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        n_slider.setRange(1, 500)
        n_slider.setValue(int(config.time_defaults["n"] / STEP))
        n_slider.param_step = STEP
        n_spin = QtWidgets.QSpinBox()
        n_spin.setKeyboardTracking(False)
        n_spin.setRange(1000, 500000)
        n_spin.setSingleStep(STEP)
        n_spin.setValue(config.time_defaults["n"])
        n_spin.param_step = STEP
        n_slider.valueChanged.connect(
            lambda val: n_spin.setValue(val * n_slider.param_step)
        )
        n_slider.valueChanged.connect(lambda: self.solve_requested.emit(False))
        n_slider.sliderReleased.connect(lambda: self.solve_requested.emit(True))
        n_spin.valueChanged.connect(
            lambda val: n_slider.setValue(int(val / n_spin.param_step))
        )
        n_spin.valueChanged.connect(self.n_changed.emit)
        n_row.addWidget(n_slider)
        n_row.addWidget(n_spin)
        self.n_slider_wrapper = QtWidgets.QWidget()
        self.n_slider_wrapper.setLayout(n_row)
        self.controls_layout.addWidget(self.n_slider_wrapper)

    def _build_t_max_slider(self, config):
        t_max_row = QtWidgets.QHBoxLayout()
        self.t_max_slider_row = t_max_row
        t_max_label = QtWidgets.QLabel("t_max")
        t_max_row.addWidget(t_max_label)
        t_max_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        t_max_slider.setRange(1, 750)
        t_max_slider.setValue(config.time_defaults["t_max"])
        t_max_slider.param_step = 1
        t_max_spin = QtWidgets.QSpinBox()
        t_max_spin.setKeyboardTracking(False)
        t_max_spin.setRange(1, 750)
        t_max_spin.setSingleStep(1)
        t_max_spin.setValue(config.time_defaults["t_max"])
        t_max_spin.param_step = 1
        t_max_slider.valueChanged.connect(
            lambda val: t_max_spin.setValue(val * t_max_slider.param_step)
        )
        t_max_slider.valueChanged.connect(lambda: self.solve_requested.emit(False))
        t_max_slider.sliderReleased.connect(lambda: self.solve_requested.emit(True))
        t_max_spin.valueChanged.connect(
            lambda val: t_max_slider.setValue(int(val / t_max_spin.param_step))
        )
        t_max_spin.valueChanged.connect(self.t_max_changed.emit)
        t_max_row.addWidget(t_max_slider)
        t_max_row.addWidget(t_max_spin)
        self.t_max_slider_wrapper = QtWidgets.QWidget()
        self.t_max_slider_wrapper.setLayout(t_max_row)
        self.controls_layout.addWidget(self.t_max_slider_wrapper)

    def _build_param_sliders(self, config):
        for p in config.params:
            row = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(p.name)
            row.addWidget(label)
            s = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            s.setRange(0, _slider_index(p.max_val, p.min_val, p.step))
            s.setValue(_slider_index(p.default, p.min_val, p.step))
            s.param_min = p.min_val
            s.param_step = p.step
            spin = QtWidgets.QDoubleSpinBox()
            spin.setKeyboardTracking(False)
            spin.setRange(p.min_val, p.max_val)
            spin.setSingleStep(p.step)
            spin.setValue(p.default)
            spin.param_min = p.min_val
            spin.param_step = p.step
            s.valueChanged.connect(
                lambda val, ss=s, sp=spin: sp.setValue(
                    _slider_value(val, ss.param_min, ss.param_step)
                )
            )
            s.valueChanged.connect(lambda: self.solve_requested.emit(False))
            s.sliderReleased.connect(lambda: self.solve_requested.emit(True))
            spin.valueChanged.connect(
                lambda val, ss=s, sp=spin: ss.setValue(
                    _slider_index(val, sp.param_min, sp.param_step)
                )
            )
            row.addWidget(s)
            row.addWidget(spin)
            wrapper = QtWidgets.QWidget()
            wrapper.setLayout(row)
            self.controls_layout.addWidget(wrapper)
            self.slider_rows.append((p, s, row, wrapper))

    def reset_to_defaults(self):
        for p, s, _, _ in self.slider_rows:
            s.setValue(_slider_index(p.default, p.min_val, p.step))
        self.solve_requested.emit(True)

    def set_traj_tail_max(self, max_val):
        max_slider = max(1, int(max_val / STEP))
        self.traj_tail_slider.setRange(1, max_slider)
        self.traj_tail_spin.setRange(STEP, max_val)

        if self.traj_tail_spin.value() > max_val:
            self.traj_tail_spin.setValue(max_val)

    def hide_standard_controls(self):
        for _, _, _, wrapper in self.slider_rows:
            wrapper.setVisible(False)
        if self.n_slider_wrapper is not None:
            self.n_slider_wrapper.setVisible(False)
        if self.t_max_slider_wrapper is not None:
            self.t_max_slider_wrapper.setVisible(False)

    def show_standard_controls(self):
        for _, _, _, wrapper in self.slider_rows:
            wrapper.setVisible(True)
        if self.n_slider_wrapper is not None:
            self.n_slider_wrapper.setVisible(True)
        if self.t_max_slider_wrapper is not None:
            self.t_max_slider_wrapper.setVisible(True)

    def get_current_values(self):
        return {
            p.name: _slider_value(s.value(), p.min_val, p.step)
            for p, s, _, _ in self.slider_rows
        }

    def set_current_values(self, values):
        for p, s, row, _ in self.slider_rows:
            if p.name not in values:
                continue
            spin = row.itemAt(2).widget()
            slider_value = _slider_index(values[p.name], p.min_val, p.step)
            with QtCore.QSignalBlocker(s), QtCore.QSignalBlocker(spin):
                s.setValue(slider_value)
                spin.setValue(_slider_value(slider_value, p.min_val, p.step))

    def set_time_values(self, n, t_max):
        if self.n_slider_row is not None:
            slider = self.n_slider_row.itemAt(1).widget()
            spin = self.n_slider_row.itemAt(2).widget()
            slider_value = int(n / spin.param_step)
            with QtCore.QSignalBlocker(slider), QtCore.QSignalBlocker(spin):
                slider.setValue(slider_value)
                spin.setValue(n)
        if self.t_max_slider_row is not None:
            slider = self.t_max_slider_row.itemAt(1).widget()
            spin = self.t_max_slider_row.itemAt(2).widget()
            slider_value = int(t_max / spin.param_step)
            with QtCore.QSignalBlocker(slider), QtCore.QSignalBlocker(spin):
                slider.setValue(slider_value)
                spin.setValue(t_max)

    def set_status(self, message, error=False):
        colour = "#ff6b6b" if error else "#a8e6a3"
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {colour}; font-size: 11px;")
        self.status_label.show()

    def clear_status(self):
        self.status_label.clear()
        self.status_label.setStyleSheet("color: transparent; font-size: 11px;")
