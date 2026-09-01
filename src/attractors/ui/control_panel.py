from pyqtgraph.Qt import QtCore, QtWidgets

from ..systems.registry import ATTRACTORS
from .data_view_panel import DataViewPanel
from .docking import AppDock as Dock
from .docking import AppDockArea as DockArea
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
        self.n_slider = None
        self.n_spin = None
        self.n_slider_wrapper = None
        self.t_max_slider = None
        self.t_max_spin = None
        self.t_max_slider_wrapper = None

        self.dropdown = QtWidgets.QComboBox()
        self.dropdown.addItems([*ATTRACTORS, "Custom"])
        self.dropdown.currentTextChanged.connect(self._on_attractor_selected)

        self.content_frame = QtWidgets.QFrame()
        self.content_frame.setObjectName("sidePanelFrame")

        content_layout = QtWidgets.QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(2, 2, 2, 2)
        content_layout.setSpacing(0)

        self.dock_area = DockArea()
        content_layout.addWidget(self.dock_area)
        self.panel_layout.addWidget(self.content_frame)

        self.controls_scroll = QtWidgets.QScrollArea()
        self.controls_scroll.setObjectName("sidePanelControlsScroll")
        self.controls_scroll.setWidgetResizable(True)
        self.controls_tab = QtWidgets.QWidget()
        self.controls_tab.setObjectName("controlPanelSliders")
        self.controls_layout = QtWidgets.QVBoxLayout(self.controls_tab)
        self.controls_layout.setContentsMargins(8, 8, 8, 8)
        self.controls_layout.setSpacing(7)
        self.controls_scroll.setWidget(self.controls_tab)

        self.controls_dock = Dock("Controls", size=(1, 360), closable=False)
        self.controls_dock.addWidget(self.controls_scroll)
        self.dock_area.addDock(self.controls_dock)

        self.data_view = DataViewPanel()
        self.data_view.setMinimumHeight(190)

        self.data_dock = Dock("Data", size=(1, 240), closable=False)
        self.data_dock.addWidget(self.data_view)
        self.dock_area.addDock(
            self.data_dock,
            position="bottom",
            relativeTo=self.controls_dock,
        )

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

        # put alpha speed and orbit speed sliders in wrapper widgets so they're so
        # spaced out nicer
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
        self.orbit_speed_wrapper = QtWidgets.QWidget()
        self.orbit_speed_wrapper.setLayout(orbit_speed_row)
        self.orbit_speed_wrapper.setVisible(False)
        self.controls_layout.addWidget(self.orbit_speed_wrapper)

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

        # put in a wrapper widget so it's visibility can be toggled
        self.traj_tail_wrapper = QtWidgets.QWidget()
        self.traj_tail_wrapper.setLayout(traj_tail_row)
        self.traj_tail_wrapper.setVisible(False)
        self.controls_layout.addWidget(self.traj_tail_wrapper)

        self.line_width_wrapper = QtWidgets.QWidget()
        self.line_width_row = QtWidgets.QHBoxLayout()
        self.line_width_row.setSpacing(10)
        self.line_width_label = QtWidgets.QLabel("Linewidth")
        self.line_width_row.addWidget(self.line_width_label)
        self.line_width_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.line_width_slider.setRange(1, 10)
        self.line_width_slider.setValue(1)
        self.line_width_spin = QtWidgets.QSpinBox()
        self.line_width_spin.setRange(1, 10)
        self.line_width_spin.setKeyboardTracking(False)
        self.line_width_spin.setValue(1)
        self.line_width_slider.valueChanged.connect(self.line_width_spin.setValue)
        self.line_width_spin.valueChanged.connect(self.line_width_slider.setValue)
        self.line_width_row.addWidget(self.line_width_slider)
        self.line_width_row.addWidget(self.line_width_spin)
        self.line_width_wrapper.setLayout(self.line_width_row)
        self.line_width_wrapper.setVisible(False)
        self.controls_layout.addWidget(self.line_width_wrapper)

    def _on_attractor_selected(self, name):
        self.set_current_attractor(name)
        self.attractor_changed.emit(name)

    def set_current_attractor(self, name):
        self.current_name = name
        with QtCore.QSignalBlocker(self.dropdown):
            index = self.dropdown.findText(name)
            if index >= 0:
                self.dropdown.setCurrentIndex(index)
        if self.right_panel is not None:
            self.right_panel.set_current_attractor(name)

    def set_right_panel(self, right_panel):
        self.right_panel = right_panel
        self.trajectory_panel = right_panel.trajectory_panel
        self.custom_panel = right_panel.custom_panel
        self.preset_panel = right_panel.preset_panel
        self.right_panel.set_current_attractor(self.current_name)

    def set_trail_options_visible(self, visible):
        self.traj_tail_wrapper.setVisible(bool(visible))

    def set_linewidth_option_visible(self, visible):
        self.line_width_wrapper.setVisible(bool(visible))

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
            self.n_slider = None
            self.n_spin = None
            self.n_slider_wrapper = None
        if self.t_max_slider_wrapper is not None:
            self.controls_layout.removeWidget(self.t_max_slider_wrapper)
            self.t_max_slider_wrapper.deleteLater()
            self.t_max_slider = None
            self.t_max_spin = None
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
        n_label = QtWidgets.QLabel("N")
        n_row.addWidget(n_label)
        self.n_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.n_slider.setRange(1, 500)
        self.n_slider.setValue(int(config.time_defaults.n / STEP))
        self.n_slider.param_step = STEP
        self.n_spin = QtWidgets.QSpinBox()
        self.n_spin.setKeyboardTracking(False)
        self.n_spin.setRange(1000, 500000)
        self.n_spin.setSingleStep(STEP)
        self.n_spin.setValue(config.time_defaults.n)
        self.n_spin.param_step = STEP
        self.n_slider.valueChanged.connect(
            lambda val: self._on_n_slider_changed(val, self.n_slider, self.n_spin)
        )
        self.n_slider.sliderReleased.connect(lambda: self.solve_requested.emit(True))
        self.n_spin.valueChanged.connect(
            lambda val: self._on_n_spin_changed(val, self.n_slider, self.n_spin)
        )
        n_row.addWidget(self.n_slider)
        n_row.addWidget(self.n_spin)

        # put n_slider and t_max sliders in wrappers so because they need to be deleted
        # and rebuilt on attractor change
        self.n_slider_wrapper = QtWidgets.QWidget()
        self.n_slider_wrapper.setLayout(n_row)
        self.controls_layout.addWidget(self.n_slider_wrapper)

    def _build_t_max_slider(self, config):
        t_max = int(config.time_defaults.t_max)
        t_max_row = QtWidgets.QHBoxLayout()
        t_max_label = QtWidgets.QLabel("t_max")
        t_max_row.addWidget(t_max_label)
        self.t_max_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.t_max_slider.setRange(1, 750)
        self.t_max_slider.setValue(t_max)
        self.t_max_slider.param_step = 1
        self.t_max_spin = QtWidgets.QSpinBox()
        self.t_max_spin.setKeyboardTracking(False)
        self.t_max_spin.setRange(1, 750)
        self.t_max_spin.setSingleStep(1)
        self.t_max_spin.setValue(t_max)
        self.t_max_spin.param_step = 1
        self.t_max_slider.valueChanged.connect(
            lambda val: self._on_t_max_slider_changed(
                val, self.t_max_slider, self.t_max_spin
            )
        )
        self.t_max_slider.sliderReleased.connect(
            lambda: self.solve_requested.emit(True)
        )
        self.t_max_spin.valueChanged.connect(
            lambda val: self._on_t_max_spin_changed(
                val, self.t_max_slider, self.t_max_spin
            )
        )
        t_max_row.addWidget(self.t_max_slider)
        t_max_row.addWidget(self.t_max_spin)
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
            self.slider_rows.append((p, s, spin, wrapper))

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
        for p, s, spin, _ in self.slider_rows:
            if p.name not in values:
                continue
            slider_value = _slider_index(values[p.name], p.min_val, p.step)
            with QtCore.QSignalBlocker(s), QtCore.QSignalBlocker(spin):
                s.setValue(slider_value)
                spin.setValue(_slider_value(slider_value, p.min_val, p.step))

    def set_time_values(self, n, t_max):
        if self.n_slider is not None:
            slider_value = int(n / self.n_spin.param_step)
            with (
                QtCore.QSignalBlocker(self.n_slider),
                QtCore.QSignalBlocker(self.n_spin),
            ):
                self.n_slider.setValue(slider_value)
                self.n_spin.setValue(n)
        if self.t_max_slider is not None:
            slider_value = int(t_max / self.t_max_spin.param_step)
            with (
                QtCore.QSignalBlocker(self.t_max_slider),
                QtCore.QSignalBlocker(self.t_max_spin),
            ):
                self.t_max_slider.setValue(slider_value)
                self.t_max_spin.setValue(t_max)
