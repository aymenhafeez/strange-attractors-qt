from functools import partial

from pyqtgraph.Qt import QtCore, QtWidgets

from .registry import ATTRACTORS
from .style import SIDE_PANEL

STEP = 1000


def _slider_index(value, min_val, step):
    return round((value - min_val) / step)


def _slider_value(index, min_val, step):
    return min_val + index * step


class ControlPanel(QtWidgets.QWidget):
    attractor_changed = QtCore.pyqtSignal(str)
    solve_requested = QtCore.pyqtSignal(bool)
    n_changed = QtCore.pyqtSignal(int)
    t_max_changed = QtCore.pyqtSignal(int)
    animation_speed_changed = QtCore.pyqtSignal(int)
    orbit_speed_changed = QtCore.pyqtSignal(int)
    traj_tail_length_changed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("controlPanel")
        self.setStyleSheet(SIDE_PANEL)

        # plain QWidget to work around objectName selector bug on QWidget subclasses
        inner = QtWidgets.QWidget()
        inner.setObjectName("controlPanel")

        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(inner)

        self.panel_layout = QtWidgets.QVBoxLayout(inner)
        self.panel_layout.setContentsMargins(4, 2, 0, 4)
        self.panel_layout.setSpacing(7)

        self.current_name = next(iter(ATTRACTORS.keys()))
        self.right_panel = None
        self.trajectory_panel = None
        self.custom_panel = None
        self.preset_panel = None
        self.slider_rows = []
        self.n_slider_row = None
        self.n_slider_wrapper = None
        self.t_max_slider_row = None
        self.t_max_slider_wrapper = None

        self.dropdown = QtWidgets.QPushButton(next(iter(ATTRACTORS.keys())))
        menu = QtWidgets.QMenu(self.dropdown)
        for name in ATTRACTORS:
            action = menu.addAction(name)
            assert action is not None
            action.triggered.connect(partial(self._on_attractor_selected, name))
        custom_action = menu.addAction("Custom")
        assert custom_action is not None
        custom_action.triggered.connect(partial(self._on_attractor_selected, "Custom"))
        self.dropdown.setMenu(menu)

        self.controls_scroll = QtWidgets.QScrollArea()
        self.controls_scroll.setObjectName("sidePanelScroll")
        self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.controls_tab = QtWidgets.QWidget()
        self.controls_layout = QtWidgets.QVBoxLayout(self.controls_tab)
        self.controls_layout.setContentsMargins(8, 8, 8, 8)
        self.controls_layout.setSpacing(7)
        self.controls_scroll.setWidget(self.controls_tab)
        self.panel_layout.addWidget(self.controls_scroll)

        options = QtWidgets.QHBoxLayout()
        options.addWidget(self.dropdown)
        self.controls_layout.addLayout(options)

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

        orbit_speed_row = QtWidgets.QHBoxLayout()
        orbit_speed_row.setSpacing(10)
        orbit_speed_label = QtWidgets.QLabel("Orbit speed")
        self.orbit_speed_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.orbit_speed_slider.setRange(1, 500)
        self.orbit_speed_slider.setValue(100)
        self.orbit_speed_spin = QtWidgets.QSpinBox()
        self.orbit_speed_spin.setKeyboardTracking(False)
        self.orbit_speed_spin.setRange(1, 500)
        self.orbit_speed_spin.setValue(100)
        self.orbit_speed_slider.valueChanged.connect(self.orbit_speed_spin.setValue)
        self.orbit_speed_spin.valueChanged.connect(self.orbit_speed_slider.setValue)
        self.orbit_speed_spin.valueChanged.connect(self.orbit_speed_changed.emit)
        orbit_speed_row.addWidget(orbit_speed_label)
        orbit_speed_row.addWidget(self.orbit_speed_slider)
        orbit_speed_row.addWidget(self.orbit_speed_spin)
        orbit_speed_wrapper = QtWidgets.QWidget()
        orbit_speed_wrapper.setLayout(orbit_speed_row)
        self.controls_layout.addWidget(orbit_speed_wrapper)

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
        self.traj_tail_wrapper = traj_tail_wrapper
        self.controls_layout.addWidget(traj_tail_wrapper)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: transparent; font-size: 11px;")
        self.status_label.hide()

        self.controls_layout.addWidget(self.status_label)

    def _on_attractor_selected(self, name):
        self.set_current_attractor(name)
        self.attractor_changed.emit(name)

    def set_current_attractor(self, name):
        self.current_name = name
        self.dropdown.setText(name)
        if self.right_panel is not None:
            self.right_panel.set_current_attractor(name)

    def set_right_panel(self, right_panel):
        self.right_panel = right_panel
        self.trajectory_panel = right_panel.trajectory_panel
        self.custom_panel = right_panel.custom_panel
        self.preset_panel = right_panel.preset_panel
        self.right_panel.set_current_attractor(self.current_name)

    def set_saved_presets(self, names, selected=None):
        self.preset_panel.set_saved_presets(names, selected)

    def current_preset_name(self):
        return self.preset_panel.current_preset_name()

    def set_preset_notes(self, notes):
        self.preset_panel.set_preset_notes(notes)

    def set_preset_summary(self, summary):
        self.preset_panel.set_preset_summary(summary)

    def get_visual_options(self):
        return {
            "orbit_speed": self.orbit_speed_spin.value(),
            "alpha": self.alpha_spin.value(),
            "animation_speed": self.anim_speed_spin.value(),
        }

    def set_visual_options(self, options):
        if "orbit_speed" in options:
            self.orbit_speed_spin.setValue(int(options["orbit_speed"]))
        if "alpha" in options:
            self.alpha_spin.setValue(int(options["alpha"]))
        if "animation_speed" in options:
            self.anim_speed_spin.setValue(int(options["animation_speed"]))

    def auto_lyapunov_enabled(self):
        return True

    def set_trail_options_visible(self, visible):
        self.traj_tail_wrapper.setVisible(bool(visible))

    def configure(self, config):
        self._clear_sliders()
        self._build_n_slider(config)
        self._build_t_max_slider(config)
        self._build_param_sliders(config)
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
        n_slider.setValue(int(config.time_defaults.n / STEP))
        n_slider.param_step = STEP
        n_spin = QtWidgets.QSpinBox()
        n_spin.setKeyboardTracking(False)
        n_spin.setRange(1000, 500000)
        n_spin.setSingleStep(STEP)
        n_spin.setValue(config.time_defaults.n)
        n_spin.param_step = STEP
        n_slider.valueChanged.connect(
            lambda val, slider=n_slider, spin=n_spin: self._on_n_slider_changed(
                val, slider, spin
            )
        )
        n_slider.sliderReleased.connect(lambda: self.solve_requested.emit(True))
        n_spin.valueChanged.connect(
            lambda val, slider=n_slider, spin=n_spin: self._on_n_spin_changed(
                val, slider, spin
            )
        )
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
        t_max_slider.setValue(config.time_defaults.t_max)
        t_max_slider.param_step = 1
        t_max_spin = QtWidgets.QSpinBox()
        t_max_spin.setKeyboardTracking(False)
        t_max_spin.setRange(1, 750)
        t_max_spin.setSingleStep(1)
        t_max_spin.setValue(config.time_defaults.t_max)
        t_max_spin.param_step = 1
        t_max_slider.valueChanged.connect(
            lambda val, slider=t_max_slider, spin=t_max_spin: (
                self._on_t_max_slider_changed(val, slider, spin)
            )
        )
        t_max_slider.sliderReleased.connect(lambda: self.solve_requested.emit(True))
        t_max_spin.valueChanged.connect(
            lambda val, slider=t_max_slider, spin=t_max_spin: (
                self._on_t_max_spin_changed(val, slider, spin)
            )
        )
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
                lambda val, ss=s, sp=spin: self._on_param_slider_changed(val, ss, sp)
            )
            s.sliderReleased.connect(lambda: self.solve_requested.emit(True))
            spin.valueChanged.connect(
                lambda val, ss=s, sp=spin: self._on_param_spin_changed(val, ss, sp)
            )
            row.addWidget(s)
            row.addWidget(spin)
            wrapper = QtWidgets.QWidget()
            wrapper.setLayout(row)
            self.controls_layout.addWidget(wrapper)
            self.slider_rows.append((p, s, row, wrapper))

    def _on_n_slider_changed(self, val, slider, spin):
        n = val * slider.param_step
        with QtCore.QSignalBlocker(spin):
            spin.setValue(n)
        self.n_changed.emit(n)
        self.solve_requested.emit(False)

    def _on_n_spin_changed(self, val, slider, spin):
        slider_value = int(val / spin.param_step)
        with QtCore.QSignalBlocker(slider):
            slider.setValue(slider_value)
        self.n_changed.emit(val)
        self.solve_requested.emit(True)

    def _on_t_max_slider_changed(self, val, slider, spin):
        t_max = val * slider.param_step
        with QtCore.QSignalBlocker(spin):
            spin.setValue(t_max)
        self.t_max_changed.emit(t_max)
        self.solve_requested.emit(False)

    def _on_t_max_spin_changed(self, val, slider, spin):
        slider_value = int(val / spin.param_step)
        with QtCore.QSignalBlocker(slider):
            slider.setValue(slider_value)
        self.t_max_changed.emit(val)
        self.solve_requested.emit(True)

    def _on_param_slider_changed(self, val, slider, spin):
        with QtCore.QSignalBlocker(spin):
            spin.setValue(_slider_value(val, slider.param_min, slider.param_step))
        self.solve_requested.emit(False)

    def _on_param_spin_changed(self, val, slider, spin):
        slider_value = _slider_index(val, spin.param_min, spin.param_step)
        with QtCore.QSignalBlocker(slider):
            slider.setValue(slider_value)
        self.solve_requested.emit(True)

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
        colour = "#ff6b6b" if error else "#178640"
        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            f"color: {colour}; font-size: 11px; font-weight: bold;"
        )
        self.status_label.show()

    def clear_status(self):
        self.status_label.clear()
        self.status_label.setStyleSheet("color: transparent; font-size: 11px;")
        self.status_label.hide()
