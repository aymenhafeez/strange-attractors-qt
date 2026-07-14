from functools import partial

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .bifurcation_dialog import BifurcationDialog
from .custom_panel import CustomPanel
from .poincare_dialog import PoincareSectionDialog
from .registry import ATTRACTORS
from .style import (
    CONTAINER,
    DROPDOWN_BOX,
    DROPDOWN_SELECTION,
    EQUATION_LABEL,
    LINE_MODE_CHECKBOX,
    LYAPUNOV_PLOT,
    SLIDER_PARAMS,
    SLIDERS,
    SPLITTER,
    STATUS_BAR,
    STATUS_IC,
    STATUS_PARAMS,
    STATUS_SYSTEM,
)
from .trajectory_panel import TrajectoryPanel
from .worker import LyapunovWorker, SolveWorker

WINDOW_SIZE = 1100
N_BINS = 96
PARTIAL_N = 40000
STEP = 1000


class Window(QtWidgets.QMainWindow):
    solve_requested = QtCore.pyqtSignal(object, dict, list, int, bool, float)
    lyapunov_requested = QtCore.pyqtSignal(object, dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Strange Attractors")

        self._initial_full_solves = 0
        self._repositioning = False
        self.current_n = 100000
        self.current_t_max = 50
        self.n_slider_row = None
        self.n_slider_wrapper = None
        self.t_max_slider_row = None
        self.t_max_slider_wrapper = None
        self.grid_items = []

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.anim_frame = 0
        self.anim_step = 200
        self.timer = QtCore.QTimer()
        self.anim_button = QtWidgets.QPushButton("▶ Play")
        self.timer.timeout.connect(self._animate_frame)

        self._solve_pending = False
        self._solve_needed = False
        self._full_needed = False
        self._solver_worker = SolveWorker()
        self._solver_thread = QtCore.QThread()
        self._solver_worker.moveToThread(self._solver_thread)
        self._solver_thread.start()
        self.solve_requested.connect(self._solver_worker.solve)
        self._solver_worker.result_ready.connect(self._on_solve_result)

        self._lyapunov_worker = LyapunovWorker()
        self._lyapunov_thread = QtCore.QThread()
        self._lyapunov_worker.moveToThread(self._lyapunov_thread)
        self._lyapunov_thread.start()
        self.lyapunov_requested.connect(self._lyapunov_worker.compute)
        self._lyapunov_worker.lyapunov_ready.connect(self._on_lyapunov_result)

        self.view = gl.GLViewWidget()
        self.container = QtWidgets.QWidget()
        self.container.setStyleSheet(CONTAINER)
        container_layout = QtWidgets.QGridLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(self.view, 0, 0)
        container_layout.setRowStretch(0, 1)
        container_layout.setColumnStretch(0, 1)

        self.equation_label = QtWidgets.QLabel("")
        self.equation_label.setStyleSheet(EQUATION_LABEL)
        container_layout.addWidget(
            self.equation_label,
            0,
            0,
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignBottom,
        )

        self.lyapunov_label = QtWidgets.QLabel("")
        self.lyapunov_label.setStyleSheet(EQUATION_LABEL)

        self.lyapunov_plot = pg.PlotWidget()
        self.lyapunov_plot.setFixedSize(300, 150)
        self.lyapunov_plot.setBackground(None)
        self.lyapunov_plot.hideAxis("bottom")
        self.lyapunov_plot.hideAxis("left")
        self.lyapunov_plot.setStyleSheet(LYAPUNOV_PLOT)
        self.curve_l1 = self.lyapunov_plot.plot([], [], pen=(255, 100, 100))
        self.curve_l2 = self.lyapunov_plot.plot([], [], pen=(100, 255, 100))
        self.curve_l3 = self.lyapunov_plot.plot([], [], pen=(100, 100, 255))

        self.lyapunov_container = QtWidgets.QWidget()
        self.lyapunov_container.setStyleSheet(LYAPUNOV_PLOT)
        lyap_layout = QtWidgets.QVBoxLayout(self.lyapunov_container)
        lyap_layout.setContentsMargins(0, 0, 0, 0)
        lyap_layout.setSpacing(2)

        lyap_layout.addWidget(
            self.lyapunov_plot, alignment=QtCore.Qt.AlignmentFlag.AlignBottom
        )
        lyap_layout.addWidget(
            self.lyapunov_label, alignment=QtCore.Qt.AlignmentFlag.AlignRight
        )

        container_layout.addWidget(
            self.lyapunov_container,
            0,
            0,
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom,
        )
        self.lyapunov_container.setVisible(False)

        status_container = QtWidgets.QWidget()
        status_container.setStyleSheet(STATUS_BAR)
        status_layout = QtWidgets.QHBoxLayout(status_container)
        status_layout.setContentsMargins(1, 0, 8, 0)
        status_layout.setSpacing(0)

        self.status_system = QtWidgets.QLabel("")
        self.status_params = QtWidgets.QLabel("")
        self.status_ic = QtWidgets.QLabel("")
        for lbl in [self.status_system, self.status_params, self.status_ic]:
            lbl.setStyleSheet(STATUS_PARAMS)
            status_layout.addWidget(lbl)

        status_container.setFixedHeight(22)
        container_layout.addWidget(status_container, 1, 0)
        self.status_system.setStyleSheet(STATUS_SYSTEM)
        self.status_ic.setStyleSheet(STATUS_IC)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setStyleSheet(SPLITTER)

        splitter.addWidget(self.container)

        layout.addWidget(splitter)

        self.panel = QtWidgets.QWidget()
        self.panel.setStyleSheet(SLIDERS)
        self.panel.setObjectName("controlPanel")
        self.panel_layout = QtWidgets.QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(8, 8, 8, 8)
        self.panel_layout.setSpacing(7)

        self.base_colour = (1.0, 1.0, 1.0)
        self.current_alpha = 1.0
        self._scatters: list[gl.GLScatterPlotItem] = []
        self._lines: list[gl.GLLinePlotItem] = []
        self._solutions: list[np.ndarray] = []
        self._trajectories: list[dict] = []

        self.options = QtWidgets.QHBoxLayout()

        self.dropdown = QtWidgets.QPushButton(list(ATTRACTORS.keys())[0])
        self.dropdown.setStyleSheet(DROPDOWN_BOX)

        menu = QtWidgets.QMenu(self.dropdown)
        menu.setStyleSheet(DROPDOWN_SELECTION)

        for name in ATTRACTORS:
            action = menu.addAction(name)
            assert action is not None
            action.triggered.connect(partial(self.on_attractor_change, name))
        custom_action = menu.addAction("Custom")
        assert custom_action is not None
        custom_action.triggered.connect(partial(self.on_attractor_change, "Custom"))
        self.dropdown.setMenu(menu)

        self.tools_button = QtWidgets.QPushButton("Tools")
        self.tools_button.setStyleSheet(DROPDOWN_BOX)
        tools_menu = QtWidgets.QMenu(self.tools_button)
        tools_menu.setStyleSheet(DROPDOWN_SELECTION)
        bifurcation_action = tools_menu.addAction("Bifurcation diagram")
        bifurcation_action.triggered.connect(self._open_bifurcation)
        poincare_action = tools_menu.addAction("Poincaré section")
        poincare_action.triggered.connect(self._open_poincare)
        self.tools_button.setMenu(tools_menu)

        self.options.addWidget(self.dropdown)
        self.options.addWidget(self.tools_button)
        self.panel_layout.addLayout(self.options)

        options_row = QtWidgets.QHBoxLayout()

        self.anim_button.clicked.connect(self.toggle_animation)
        options_row.addWidget(self.anim_button)
        options_row.addStretch(1)

        self.line_mode = QtWidgets.QCheckBox("Line")
        self.line_mode.setChecked(False)
        self.line_mode.setStyleSheet(LINE_MODE_CHECKBOX)
        self.line_mode.toggled.connect(self._toggle_line_mode)
        options_row.addWidget(self.line_mode)

        self.trail_mode = QtWidgets.QCheckBox("Trail")
        self.trail_mode.setChecked(False)
        self.trail_mode.setStyleSheet(LINE_MODE_CHECKBOX)
        self.trail_mode.toggled.connect(self._refresh_colours)
        options_row.addWidget(self.trail_mode)

        self.show_grid = QtWidgets.QCheckBox("Grid")
        self.show_grid.setChecked(True)
        self.show_grid.setStyleSheet(LINE_MODE_CHECKBOX)
        self.show_grid.toggled.connect((self._toggle_grid))

        options_row.addWidget(self.show_grid)
        self.panel_layout.addLayout(options_row)

        alpha_row = QtWidgets.QHBoxLayout()
        alpha_row.setSpacing(10)
        alpha_label = QtWidgets.QLabel("α ")
        alpha_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        alpha_slider.setRange(0, 100)
        alpha_slider.setValue(100)
        alpha_spin = QtWidgets.QSpinBox()
        alpha_spin.setKeyboardTracking(False)
        alpha_spin.setRange(0, 100)
        alpha_spin.setValue(100)
        alpha_slider.valueChanged.connect(self._update_alpha)
        alpha_spin.valueChanged.connect(self._update_alpha)
        alpha_slider.valueChanged.connect(alpha_spin.setValue)
        alpha_spin.valueChanged.connect(alpha_slider.setValue)
        alpha_row.addWidget(alpha_label)
        alpha_row.addWidget(alpha_slider)
        alpha_row.addWidget(alpha_spin)
        alpha_wrapper = QtWidgets.QWidget()
        alpha_wrapper.setLayout(alpha_row)
        self.panel_layout.addWidget(alpha_wrapper)

        splitter.addWidget(self.panel)
        splitter.setSizes([int(WINDOW_SIZE * 0.7), int(WINDOW_SIZE * 0.3)])

        self.current_name = list(ATTRACTORS.keys())[0]
        self.slider_rows = []

        self._custom_config = None
        self.custom_panel = CustomPanel(self.container)
        self.custom_panel.compile_requested.connect(self._on_custom_compile)
        self.custom_panel.setVisible(False)
        self.custom_panel.raise_()

        self.trajectory_panel = TrajectoryPanel(self.container)
        self.trajectory_panel.trajectories_changed.connect(
            self._on_trajectories_changed
        )
        self.trajectory_panel.styles_changed.connect(self._on_trajectory_styles_changed)
        self.trajectory_panel.raise_()

        self.container.installEventFilter(self)
        self.custom_panel.installEventFilter(self)
        self.trajectory_panel.installEventFilter(self)

        self.projection_container = QtWidgets.QWidget()
        proj_layout = QtWidgets.QVBoxLayout(self.projection_container)
        proj_layout.setContentsMargins(0, 0, 0, 0)
        proj_layout.setSpacing(3)

        self.image_items = {}
        for key, (lh, lv) in [
            ("XY", ("X", "Y")),
            ("XZ", ("X", "Z")),
            ("YZ", ("Y", "Z")),
        ]:
            pw = pg.PlotWidget()
            pw.showAxis("bottom", False)
            pw.showAxis("left", False)
            pw.showAxis("top", False)
            pw.showAxis("right", False)
            pw.setLabel("bottom", lh)
            pw.setLabel("left", lv)
            pw.getPlotItem().setContentsMargins(0, 10, 0, 0)
            pw.getViewBox().setAspectLocked(True)
            img = pg.ImageItem()
            cmap = pg.colormap.get("CET-L1")
            img.setLookupTable(cmap.getLookupTable())
            pw.addItem(img)
            self.image_items[key] = (img, pw)
            pw.getPlotItem().addColorBar(
                img,
                values=(0, 10),
                colorMap=pg.colormap.get("CET-L1"),
                width=10,
            )
            proj_layout.addWidget(pw)

        self._rebuild_view(self.current_name)

        self.grid_half_size = 30.0
        self.grid_items = []
        self._build_grid(self.grid_half_size)
        self._reposition_overlays()

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition_overlays()

    def eventFilter(self, obj, event):
        if obj is self.container and event.type() == QtCore.QEvent.Type.Resize:
            self._reposition_overlays()
        if (
            obj in (self.custom_panel, self.trajectory_panel)
            and event.type() == QtCore.QEvent.Type.Resize
        ):
            self._reposition_overlays()
        return super().eventFilter(obj, event)

    def _reposition_overlays(self):
        if self._repositioning:
            return
        self._repositioning = True
        margin = 8
        self.view.lower()
        self.custom_panel.adjustSize()
        self.custom_panel.move(margin, margin)
        self.custom_panel.raise_()
        self.trajectory_panel.adjustSize()
        x = self.container.width() - self.trajectory_panel.width() - margin
        self.trajectory_panel.move(x, margin)
        self.trajectory_panel.raise_()
        self._repositioning = False

    def _build_grid(self, half_size):
        for item in self.grid_items:
            self.view.removeItem(item)
        self.grid_items.clear()

        is_visible = self.show_grid.isChecked()

        self.grid_half_size = half_size
        ideal_spacing = half_size / 4
        spacing = max(
            1.0, round(ideal_spacing, -int(np.floor(np.log10(ideal_spacing))))
        )
        num_divisions = max(4, int(round(half_size * 2 / spacing)))
        spacing = half_size * 2 / num_divisions

        grid_faces = [
            ("XY", [], (0, 0, -half_size)),
            ("YZ", [(90, 1, 0, 0)], (0, -half_size, 0)),
            ("XZ", [(90, 0, 1, 0)], (-half_size, 0, 0)),
            ("YX", [], (0, 0, half_size)),
            ("ZY", [(90, 1, 0, 0)], (0, half_size, 0)),
            ("ZX", [(90, 0, 1, 0)], (half_size, 0, 0)),
        ]
        tick_positions = np.linspace(-half_size, half_size, num_divisions + 1)
        tick_values = [round(v, 0) for v in tick_positions]

        for i, (_, rotations, (dx, dy, dz)) in enumerate(grid_faces):
            g = gl.GLGridItem()
            g.setSize(x=half_size * 2, y=half_size * 2, z=1)
            g.setSpacing(x=spacing, y=spacing, z=1)
            for angle, *axis in rotations:
                g.rotate(angle, *axis)
            g.translate(dx, dy, dz)
            self.view.addItem(g)
            self.grid_items.append(g)
            g.setVisible(is_visible)

            if i < 3:
                for val in tick_values:
                    if abs(val) < 1e-5:
                        continue

                    offset = spacing * 0.3

                    t1 = gl.GLTextItem(
                        pos=[val, -offset, 0],
                        text=str(val),
                        color=(255, 255, 255, 100),
                        font=QtGui.QFont("Sans", 10),
                    )
                    t2 = gl.GLTextItem(
                        pos=[-offset, val, 0],
                        text=str(val),
                        color=(255, 255, 255, 100),
                        font=QtGui.QFont("Sans", 10),
                    )

                    for angle, *axis in rotations:
                        t1.rotate(angle, *axis)
                        t2.rotate(angle, *axis)

                    t1.translate(dx, dy, dz)
                    t2.translate(dx, dy, dz)

                    t1.setVisible(is_visible)
                    t2.setVisible(is_visible)

                    self.view.addItem(t1)
                    self.view.addItem(t2)
                    self.grid_items.append(t1)
                    self.grid_items.append(t2)

    def _sync_gl_items(self, n: int):
        line_mode = self.line_mode.isChecked()
        while len(self._scatters) < n:
            scatter = gl.GLScatterPlotItem(size=1.0)
            scatter.setGLOptions("additive")
            scatter.setVisible(not line_mode)
            self.view.addItem(scatter)
            self._scatters.append(scatter)
            line = gl.GLLinePlotItem()
            line.setVisible(line_mode)
            self.view.addItem(line)
            self._lines.append(line)
        while len(self._scatters) > n:
            self.view.removeItem(self._scatters.pop())
            self.view.removeItem(self._lines.pop())

    def toggle_animation(self):
        if self.timer.isActive():
            self.timer.stop()
            self.anim_button.setText("▶ Play")
        else:
            self.anim_frame = 0
            self.timer.start(16)
            self.anim_button.setText("■ Stop")

    def _animate_frame(self):
        if not self._solutions:
            return

        sol0 = self._solutions[0]
        frame = min(self.anim_frame + self.anim_step, len(sol0))
        self.anim_frame = frame

        all_segments = []
        for i, sol in enumerate(self._solutions):
            segment = sol[:frame]
            base_colour, alpha = self._get_traj_colour_alpha(i)

            if self.trail_mode.isChecked():
                c = self._plot_trail(len(segment), alpha, base_colour)
            else:
                c = np.full((len(segment), 4), (*base_colour, alpha))

            if i < len(self._scatters):
                self._scatters[i].setData(pos=segment, color=c)
                self._lines[i].setData(pos=segment, color=c)
            all_segments.append(segment)

        if all_segments:
            all_pts = np.concatenate(all_segments, axis=0)
            x, y, z = all_pts.T
            self._update_projections(x, y, z)

        if frame >= len(sol0):
            self.timer.stop()
            self.anim_button.setText("▶ Play")

    def _rebuild_view(self, name):
        if name == "Custom":
            self._rebuild_view_custom()
            return
        self._rebuild_view_from_config(ATTRACTORS[name])

    def _rebuild_view_custom(self):
        self.timer.stop()
        self.anim_button.setText("▶ Play")

        self._hide_standard_controls()
        self.custom_panel.setVisible(True)

        if self._custom_config is not None:
            self._apply_config_to_view(self._custom_config)

    def _hide_standard_controls(self):
        for _, _, _, wrapper in self.slider_rows:
            wrapper.setVisible(False)
        if self.n_slider_wrapper is not None:
            self.n_slider_wrapper.setVisible(False)
        if self.t_max_slider_wrapper is not None:
            self.t_max_slider_wrapper.setVisible(False)

    def _show_standard_controls(self):
        for _, _, _, wrapper in self.slider_rows:
            wrapper.setVisible(True)
        if self.n_slider_wrapper is not None:
            self.n_slider_wrapper.setVisible(True)
        if self.t_max_slider_wrapper is not None:
            self.t_max_slider_wrapper.setVisible(True)

    def _rebuild_view_from_config(self, config):
        self.timer.stop()
        self.anim_button.setText("▶ Play")

        self.custom_panel.setVisible(False)
        self._show_standard_controls()

        self.panel_layout.removeWidget(self.projection_container)

        for *_, wrapper in self.slider_rows:
            self.panel_layout.removeWidget(wrapper)
            wrapper.setParent(None)
            wrapper.deleteLater()
        self.slider_rows.clear()

        while self.panel_layout.count():
            item = self.panel_layout.itemAt(self.panel_layout.count() - 1)
            if item is not None and item.spacerItem():
                self.panel_layout.takeAt(self.panel_layout.count() - 1)
            else:
                break

        self._apply_config_to_view(config)

    def _apply_config_to_view(self, config):
        self.equation_label.setText(config.equation_text)
        self.equation_label.setVisible(bool(config.equation_text))
        self.view.setCameraPosition(
            pos=QtGui.QVector3D(0, 0, 0),
            distance=config.camera_distance,
            elevation=config.camera_elevation,
            azimuth=config.camera_azimuth,
        )
        self.view.opts["center"] = QtGui.QVector3D(
            self.view.opts["center"].x(),
            self.view.opts["center"].y(),
            self.view.opts["center"].z() + config.pan,
        )

        if self.n_slider_wrapper is not None:
            self.panel_layout.removeWidget(self.n_slider_wrapper)
            self.n_slider_wrapper.setParent(None)
            self.n_slider_wrapper.deleteLater()
            self.n_slider_row = None
            self.n_slider_wrapper = None

        n_row = QtWidgets.QHBoxLayout()
        self.n_slider_row = n_row
        n_label = QtWidgets.QLabel("N")
        n_label.setStyleSheet("color: white;")
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
        n_slider.spin = n_spin
        n_spin.slider = n_slider
        n_slider.valueChanged.connect(partial(self._on_slider_moved, n_slider, n_spin))
        n_slider.valueChanged.connect(self._on_slider_tick)
        n_slider.sliderReleased.connect(self._on_slider_released)
        n_spin.valueChanged.connect(partial(self._on_spin_changed, n_spin, n_slider))
        n_spin.valueChanged.connect(self._on_n_changed)
        n_row.addWidget(n_slider)
        n_row.addWidget(n_spin)
        self.n_slider_wrapper = QtWidgets.QWidget()
        self.n_slider_wrapper.setLayout(n_row)
        self.panel_layout.addWidget(self.n_slider_wrapper)
        self.current_n = config.time_defaults["n"]

        if self.t_max_slider_wrapper is not None:
            self.panel_layout.removeWidget(self.t_max_slider_wrapper)
            self.t_max_slider_wrapper.setParent(None)
            self.t_max_slider_wrapper.deleteLater()
            self.t_max_slider_row = None
            self.t_max_slider_wrapper = None

        t_max_row = QtWidgets.QHBoxLayout()
        self.t_max_slider_row = t_max_row
        t_max_label = QtWidgets.QLabel("t_max")
        t_max_label.setStyleSheet("color: white;")
        t_max_row.addWidget(t_max_label)
        t_max_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        t_max_slider.setRange(1, 500)
        t_max_slider.setValue(config.time_defaults["t_max"])
        t_max_slider.param_step = 1
        t_max_spin = QtWidgets.QSpinBox()
        t_max_spin.setKeyboardTracking(False)
        t_max_spin.setRange(1, 5000)
        t_max_spin.setSingleStep(1)
        t_max_spin.setValue(config.time_defaults["t_max"])
        t_max_spin.param_step = 1
        t_max_slider.spin = t_max_spin
        t_max_spin.slider = t_max_slider
        t_max_slider.valueChanged.connect(
            partial(self._on_slider_moved, t_max_slider, t_max_spin)
        )
        t_max_slider.valueChanged.connect(self._on_slider_tick)
        t_max_slider.sliderReleased.connect(self._on_slider_released)
        t_max_spin.valueChanged.connect(
            partial(self._on_spin_changed, t_max_spin, t_max_slider)
        )
        t_max_spin.valueChanged.connect(self._on_t_max_changed)
        t_max_row.addWidget(t_max_slider)
        t_max_row.addWidget(t_max_spin)
        self.t_max_slider_wrapper = QtWidgets.QWidget()
        self.t_max_slider_wrapper.setLayout(t_max_row)
        self.panel_layout.addWidget(self.t_max_slider_wrapper)
        self.current_t_max = config.time_defaults["t_max"]

        for p in config.params:
            row = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(p.name)
            label.setStyleSheet(SLIDER_PARAMS)
            row.addWidget(label)
            s = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            s.setRange(int(p.min_val / p.step), int(p.max_val / p.step))
            s.setValue(int(p.default / p.step))
            s.param_step = p.step
            spin = QtWidgets.QDoubleSpinBox()
            spin.setKeyboardTracking(False)
            spin.setRange(p.min_val, p.max_val)
            spin.setSingleStep(p.step)
            spin.setValue(p.default)
            spin.param_step = p.step
            s.spin = spin
            spin.slider = s
            s.valueChanged.connect(partial(self._on_slider_moved, s, spin))
            s.valueChanged.connect(self._on_slider_tick)
            s.sliderReleased.connect(self._on_slider_released)
            spin.valueChanged.connect(partial(self._on_spin_changed, spin, s))
            row.addWidget(s)
            row.addWidget(spin)
            wrapper = QtWidgets.QWidget()
            wrapper.setLayout(row)
            self.panel_layout.addWidget(wrapper)
            self.slider_rows.append((p, s, row, wrapper))

        self.lyapunov_label.setText("")
        self.lyapunov_container.setVisible(False)

        self.panel_layout.addStretch()
        self.panel_layout.addWidget(self.projection_container)
        self.trajectory_panel.reset(config)
        self._update_plot()

    def on_attractor_change(self, name):
        self.current_name = name
        self.dropdown.setText(name)
        self._rebuild_view(name)

    def _on_custom_compile(self, config):
        self._custom_config = config

        for *_, wrapper in self.slider_rows:
            self.panel_layout.removeWidget(wrapper)
            wrapper.setParent(None)
            wrapper.deleteLater()
        self.slider_rows.clear()

        self._apply_config_to_view(config)

    def _get_current_config_and_values(self):
        if self.current_name == "Custom":
            config = self._custom_config
        else:
            config = ATTRACTORS[self.current_name]
        if config is None:
            return None, {}
        values = {p.name: p.step * s.value() for p, s, _, _ in self.slider_rows}
        return config, values

    def _update_plot(self):
        self.timer.stop()
        self.anim_button.setText("▶ Play")
        self._dispatch_solve(full=True)

        config, values = self._get_current_config_and_values()
        if config is None:
            return

        formatted_params = "  ".join(f"{k}: {v:.2f}" for k, v in sorted(values.items()))
        self.status_system.setText(f"<b>SYSTEM</b>: {config.name}")
        self.status_system.setToolTip(f"{config.description}")
        self.status_params.setText(f"<b>PARAMS</b>: {formatted_params}")
        self.status_ic.setText(f"<b>IC</b>: {config.initial_conditions}")

    def _update_projections(self, x, y, z):
        for key, (data_h, data_v) in {"XY": (x, y), "XZ": (x, z), "YZ": (y, z)}.items():
            img, pw = self.image_items[key]
            heatmap, xedges, yedges = np.histogram2d(
                data_h, data_v, bins=N_BINS, density=True
            )
            img.setImage(np.log1p(heatmap))

            x_min, x_max = xedges[0], xedges[-1]
            y_min, y_max = yedges[0], yedges[-1]
            img.setRect(pg.QtCore.QRectF(x_min, y_min, x_max - x_min, y_max - y_min))
            pw.autoRange()

    def _reapply_projections(self):
        if self._solutions:
            all_sol = np.concatenate(self._solutions, axis=0)
            x, y, z = all_sol.T
            self._update_projections(x, y, z)

    def _update_alpha(self, val):
        self.current_alpha = val / 100.0
        self._refresh_colours()

    def _toggle_line_mode(self, checked):
        for scatter, line in zip(self._scatters, self._lines):
            line.setVisible(checked)
            scatter.setVisible(not checked)

    def _toggle_grid(self, checked):
        for item in self.grid_items:
            item.setVisible(checked)

    def _on_slider_tick(self):
        self._solve_needed = True
        self._dispatch_solve()

    def _on_slider_released(self):
        self._solve_needed = True
        self._full_needed = True
        self._dispatch_solve(full=True)

    def _dispatch_solve(self, full=False):
        if self._solve_pending:
            return

        self._solve_pending = True
        self._solve_needed = False

        config, values = self._get_current_config_and_values()
        if config is None:
            self._solve_pending = False
            return

        user_n = self.current_n or config.time_defaults["n"]
        t_max = self.current_t_max

        ics = [t["ic"] for t in self._trajectories] or [config.initial_conditions]
        dispatch_n = user_n if full else min(user_n, PARTIAL_N)
        self.solve_requested.emit(config, values, ics, dispatch_n, not full, t_max)

    def _on_solve_result(self, solutions, is_partial):
        self._solve_pending = False

        if solutions is None:
            return

        if not is_partial:
            self._solutions = solutions

        self._sync_gl_items(len(solutions))
        line_mode = self.line_mode.isChecked()

        for i, sol in enumerate(solutions):
            base_colour, alpha = self._get_traj_colour_alpha(i)

            if self.trail_mode.isChecked():
                c = self._plot_trail(len(sol), alpha, base_colour)
            else:
                c = np.full((len(sol), 4), (*base_colour, alpha))

            self._scatters[i].setData(pos=sol, color=c)
            self._scatters[i].setVisible(not line_mode)
            self._lines[i].setData(pos=sol, color=c)
            self._lines[i].setVisible(line_mode)

        if not is_partial:
            all_sol = np.concatenate(solutions, axis=0)
            x, y, z = all_sol.T
            self._update_projections(x, y, z)
            config, values = self._get_current_config_and_values()

            if config is not None:
                self.lyapunov_requested.emit(config, values)

            if self._initial_full_solves == 0:
                QtCore.QTimer.singleShot(0, self._reapply_projections)
                self._initial_full_solves += 1

            new_half = min(float(np.max(np.abs(solutions[0]))) * 3, 500.0)
            if (
                abs(new_half - self.grid_half_size) / max(self.grid_half_size, 1e-6)
                > 0.1
            ):
                self._build_grid(new_half)

        self._refresh_colours()

        if self._solve_needed:
            self._solve_needed = False
            full = self._full_needed
            self._full_needed = False
            self._dispatch_solve(full=full)

    def _on_slider_moved(self, s, spin, val):
        self.timer.stop()
        self.anim_button.setText("▶ Play")
        spin.setValue(val * s.param_step)

    def _on_spin_changed(self, spin, s, val):
        self.timer.stop()
        self.anim_button.setText("▶ Play")
        s.setValue(int(val / spin.param_step))

    def _on_n_changed(self, val):
        self.current_n = val

    def _on_t_max_changed(self, val):
        self.current_t_max = val

    def _get_traj_colour_alpha(self, i: int):
        traj = self._trajectories[i] if i < len(self._trajectories) else None
        if traj is not None:
            qc = traj["colour"]
            base_colour = (qc.redF(), qc.greenF(), qc.blueF())
            alpha = self.current_alpha * traj.get("alpha", 1.0)
        else:
            base_colour = self.base_colour
            alpha = self.current_alpha
        return base_colour, alpha

    def _plot_trail(self, n, alpha=1.0, base_colour=None):
        if base_colour is None:
            base_colour = self.base_colour
        colour = np.zeros((n, 4))
        colour[:, 0] = np.linspace(0.2, base_colour[0], n)
        colour[:, 1] = np.linspace(0.2, base_colour[1], n)
        colour[:, 2] = np.linspace(0.5, base_colour[2], n)
        colour[:, 3] = np.linspace(0.0, alpha, n)
        return colour

    def _refresh_colours(self):
        if not self._solutions:
            return

        line_mode = self.line_mode.isChecked()
        for i, sol in enumerate(self._solutions):
            if i >= len(self._scatters):
                break
            base_colour, alpha = self._get_traj_colour_alpha(i)

            if self.trail_mode.isChecked():
                c = self._plot_trail(len(sol), alpha, base_colour)
            else:
                c = np.full((len(sol), 4), (*base_colour, alpha))

            self._scatters[i].setData(color=c)
            self._scatters[i].setVisible(not line_mode)
            self._lines[i].setData(color=c)
            self._lines[i].setVisible(line_mode)

    def _on_trajectories_changed(self, trajectories: list[dict]):
        self._trajectories = trajectories
        self._solve_needed = True
        self._full_needed = True
        self._dispatch_solve(full=True)

    def _on_trajectory_styles_changed(self, trajectories: list[dict]):
        self._trajectories = trajectories
        self._refresh_colours()

    def _on_lyapunov_result(self, lyap, ky_dim, t_hist, lyap_hist):
        self.lyapunov_label.setText(
            f"λ = ({lyap[0]:+.2f}, {lyap[1]:+.2f}, {lyap[2]:+.2f})  D_KY = {ky_dim:.2f}"
        )

        self.lyapunov_container.setVisible(True)
        self.curve_l1.setData(t_hist, lyap_hist[:, 0])
        self.curve_l2.setData(t_hist, lyap_hist[:, 1])
        self.curve_l3.setData(t_hist, lyap_hist[:, 2])

    def _open_poincare(self):
        sol = self._solutions[0].copy() if self._solutions else None
        dialog = PoincareSectionDialog(self, sol, self)
        dialog.show()

    def _open_bifurcation(self):
        config, values = self._get_current_config_and_values()
        if config is None:
            return
        dialog = BifurcationDialog(config, values, self)
        dialog.show()

    def closeEvent(self, a0: QtGui.QCloseEvent | None) -> None:
        self.timer.stop()
        self._solver_worker._cancel = True
        self._solver_thread.quit()
        self._solver_thread.wait()
        self._lyapunov_worker._cancel = True
        self._lyapunov_thread.quit()
        self._lyapunov_thread.wait()
        super().closeEvent(a0)
