from functools import partial

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .bifurcation_dialog import BifurcationDialog
from .registry import ATTRACTORS
from .style import (
    ALPHA_SLIDER,
    ATTRACTOR_INFO,
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
from .worker import LyapunovWorker, SolveWorker

WINDOW_SIZE = 1100
N_BINS = 96
PARTIAL_N = 40000


class Window(QtWidgets.QMainWindow):
    solve_requested = QtCore.pyqtSignal(object, dict, object)
    lyapunov_requested = QtCore.pyqtSignal(object, dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Strange Attractors")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.anim_frame = 0
        self.anim_step = 200
        self.full_solution = None
        self.timer = QtCore.QTimer()
        self.anim_button = QtWidgets.QPushButton("Play")
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
        container = QtWidgets.QWidget()
        container.setStyleSheet(CONTAINER)
        container_layout = QtWidgets.QGridLayout(container)
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

        splitter.addWidget(container)

        layout.addWidget(splitter)

        grid_faces = [
            ("XY", [], (0, 0, -100)),
            ("YZ", [(90, 1, 0, 0)], (0, -100, 0)),
            ("XZ", [(90, 0, 1, 0)], (-100, 0, 0)),
            ("YX", [], (0, 0, 100)),
            ("ZY", [(90, 1, 0, 0)], (0, 100, 0)),
            ("ZX", [(90, 0, 1, 0)], (100, 0, 0)),
        ]
        tick_values = list(range(-100, 100, 20))

        for _, rotations, (dx, dy, dz) in grid_faces:
            g = gl.GLGridItem()
            g.setSize(x=200, y=200, z=1)
            g.setSpacing(x=20, y=20, z=1)
            for angle, *axis in rotations:
                g.rotate(angle, *axis)
            g.translate(dx, dy, dz)
            self.view.addItem(g)

            for val in tick_values:
                if val == 0:
                    continue

                t1 = gl.GLTextItem(
                    pos=[val, -10, 0],
                    text=str(val),
                    color=(255, 255, 255, 100),
                    font=QtGui.QFont("Sans", 10),
                )
                t2 = gl.GLTextItem(
                    pos=[-10, val, 0],
                    text=str(val),
                    color=(255, 255, 255, 100),
                    font=QtGui.QFont("Sans", 10),
                )

                for angle, *axis in rotations:
                    t1.rotate(angle, *axis)
                    t2.rotate(angle, *axis)

                t1.translate(dx, dy, dz)
                t2.translate(dx, dy, dz)

                self.view.addItem(t1)
                self.view.addItem(t2)

        self.panel = QtWidgets.QWidget()
        self.panel.setStyleSheet(SLIDERS)
        self.panel.setObjectName("controlPanel")
        self.panel_layout = QtWidgets.QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(8, 8, 8, 8)
        self.panel_layout.setSpacing(15)

        self.base_colour = (1.0, 1.0, 1.0)
        self.current_alpha = 1.0
        self.scatter = gl.GLScatterPlotItem(
            pos=np.zeros((1, 3)), color=(*self.base_colour, 1.0), size=1.0, pxMode=True
        )
        self.line = gl.GLLinePlotItem(
            pos=np.zeros((1, 3)), color=(*self.base_colour, 1.0), width=1.0
        )
        self.scatter.setVisible(True)
        self.line.setVisible(False)
        self.view.addItem(self.scatter)
        self.view.addItem(self.line)

        self.dropdown = QtWidgets.QPushButton(list(ATTRACTORS.keys())[0])
        self.dropdown.setStyleSheet(DROPDOWN_BOX)

        self.tools_button = QtWidgets.QPushButton("Tools")
        self.tools_button.setStyleSheet(DROPDOWN_BOX)
        tools_menu = QtWidgets.QMenu(self.tools_button)
        tools_menu.setStyleSheet(DROPDOWN_SELECTION)
        bifurcation_action = tools_menu.addAction("Bifurcation diagram")
        bifurcation_action.triggered.connect(self._open_bifurcation)
        self.tools_button.setMenu(tools_menu)
        self.panel_layout.addWidget(self.tools_button)

        menu = QtWidgets.QMenu(self.dropdown)
        menu.setStyleSheet(DROPDOWN_SELECTION)

        for name in ATTRACTORS:
            action = menu.addAction(name)
            assert action is not None
            action.triggered.connect(partial(self.on_attractor_change, name))
        self.dropdown.setMenu(menu)
        self.panel_layout.addWidget(self.dropdown)

        self.anim_button.clicked.connect(self.toggle_animation)
        self.panel_layout.addWidget(self.anim_button)

        alpha_row = QtWidgets.QHBoxLayout()
        alpha_label = QtWidgets.QLabel("α ")
        alpha_label.setStyleSheet(ALPHA_SLIDER)
        alpha_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        alpha_slider.setRange(0, 100)
        alpha_slider.setValue(100)
        alpha_slider.valueChanged.connect(self._update_alpha)
        alpha_row.addWidget(alpha_label)
        alpha_row.addWidget(alpha_slider)
        self.panel_layout.addLayout(alpha_row)

        self.line_mode = QtWidgets.QCheckBox("Line")
        self.line_mode.setChecked(False)
        self.line_mode.setStyleSheet(LINE_MODE_CHECKBOX)
        self.line_mode.toggled.connect(self._toggle_line_mode)
        alpha_row.addWidget(self.line_mode)

        self.trail_mode = QtWidgets.QCheckBox("Trail")
        self.trail_mode.setChecked(False)
        self.trail_mode.setStyleSheet(LINE_MODE_CHECKBOX)
        self.trail_mode.toggled.connect(self._refresh_colours)
        alpha_row.addWidget(self.trail_mode)

        splitter.addWidget(self.panel)
        splitter.setSizes([int(WINDOW_SIZE * 0.7), int(WINDOW_SIZE * 0.3)])

        self.current_name = list(ATTRACTORS.keys())[0]
        self.slider_rows = []

        self.info_label = QtWidgets.QLabel("")
        self.info_label.setStyleSheet(ATTRACTOR_INFO)
        self.info_label.setWordWrap(True)

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
            pw.getViewBox().setContentsMargins(0, 0, 0, 0)
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

        self.panel_layout.addWidget(self.info_label)

    def toggle_animation(self):
        if self.timer.isActive():
            self.timer.stop()
            self.anim_button.setText("Play")
        else:
            self.anim_frame = 0
            self.timer.start(16)
            self.anim_button.setText("Pause")

    def _animate_frame(self):
        sol = self.full_solution
        if sol is None:
            return

        frame = min(self.anim_frame + self.anim_step, len(sol))
        self.anim_frame = frame
        segment = sol[:frame]
        x, y, z = segment.T

        if self.trail_mode.isChecked():
            c = self._plot_trail(len(segment), self.current_alpha)
        else:
            c = np.full((len(segment), 4), (*self.base_colour, self.current_alpha))

        self.scatter.setData(pos=segment, color=c)
        self.line.setData(pos=segment, color=c)
        self._update_projections(x, y, z)

        if frame >= len(sol):
            self.timer.stop()
            self.anim_button.setText("Play")

    def _rebuild_view(self, name):
        self.timer.stop()
        self.anim_button.setText("Play")

        self.panel_layout.removeWidget(self.info_label)
        self.panel_layout.removeWidget(self.projection_container)

        for _, _, row_layout in self.slider_rows:
            while row_layout.count():
                item = row_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
            self.panel_layout.removeItem(row_layout)
        self.slider_rows.clear()

        while self.panel_layout.count():
            item = self.panel_layout.itemAt(self.panel_layout.count() - 1)
            if item is not None and item.spacerItem():
                self.panel_layout.takeAt(self.panel_layout.count() - 1)
            else:
                break

        config = ATTRACTORS[name]
        self.info_label.setText(config.description)
        self.info_label.setVisible(bool(config.description))
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
            self.slider_rows.append((p, s, row))
            self.panel_layout.addLayout(row)

        self.lyapunov_label.setText("")
        self.lyapunov_container.setVisible(False)

        self.panel_layout.addStretch()
        self.panel_layout.addWidget(self.projection_container)
        self.panel_layout.addWidget(self.info_label)
        self._update_plot()

    def on_attractor_change(self, name):
        self.current_name = name
        self.dropdown.setText(name)
        self._rebuild_view(name)

    def _update_plot(self):
        self.timer.stop()
        self.anim_button.setText("Play")
        self._dispatch_solve(full=True)

        config = ATTRACTORS[self.current_name]
        values = {p.name: p.step * s.value() for p, s, _ in self.slider_rows}

        formatted_params = "  ".join(f"{k}: {v:.2f}" for k, v in sorted(values.items()))
        self.status_system.setText(f"<b>SYSTEM</b>: {config.name}")
        self.status_params.setText(f"<b>PARAMS</b>: {formatted_params}")
        self.status_ic.setText(f"<b>IC</b>: {config.initial_conditions}")

    def _update_projections(self, x, y, z):
        for key, (data_h, data_v) in {"XY": (x, y), "XZ": (x, z), "YZ": (y, z)}.items():
            img, pw = self.image_items[key]
            heatmap, xedges, yedges = np.histogram2d(data_h, data_v, bins=N_BINS)
            img.setImage(np.log1p(heatmap))

            x_min, x_max = xedges[0], xedges[-1]
            y_min, y_max = yedges[0], yedges[-1]
            img.setRect(pg.QtCore.QRectF(x_min, y_min, x_max - x_min, y_max - y_min))
            pw.autoRange()

    def _update_alpha(self, val):
        self.current_alpha = val / 100.0
        self._refresh_colours()

    def _toggle_line_mode(self, checked):
        self.line.setVisible(checked)
        self.scatter.setVisible(not checked)

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
        config = ATTRACTORS[self.current_name]
        values = {p.name: p.step * s.value() for p, s, _ in self.slider_rows}
        n = None if full else min(config.time_defaults["n"], PARTIAL_N)
        self.solve_requested.emit(config, values, n)

    def _on_solve_result(self, sol, is_partial):
        self._solve_pending = False

        if sol is None:
            return

        self.full_solution = sol
        x, y, z = sol.T
        self.scatter.setData(pos=sol)
        self.line.setData(pos=sol)

        if not is_partial:
            self._update_projections(x, y, z)
            config = ATTRACTORS[self.current_name]
            values = {p.name: p.step * s.value() for p, s, _ in self.slider_rows}
            self.lyapunov_requested.emit(config, values)

        self._refresh_colours()

        if self._solve_needed:
            self._solve_needed = False
            full = self._full_needed
            self._full_needed = False
            self._dispatch_solve(full=full)

    def _on_slider_moved(self, s, spin, val):
        self.timer.stop()
        self.anim_button.setText("Play")
        spin.setValue(val * s.param_step)

    def _on_spin_changed(self, spin, s, val):
        self.timer.stop()
        self.anim_button.setText("Play")
        s.setValue(int(val / spin.param_step))

    def _plot_trail(self, n, alpha=1.0):
        colour = np.zeros((n, 4))

        colour[:, 0] = np.linspace(0.2, self.base_colour[0], n)
        colour[:, 1] = np.linspace(0.2, self.base_colour[1], n)
        colour[:, 2] = np.linspace(0.5, self.base_colour[2], n)
        colour[:, 3] = np.linspace(0.0, alpha, n)

        return colour

    def _refresh_colours(self):
        solution = self.full_solution

        if solution is None:
            return

        if self.trail_mode.isChecked():
            c = self._plot_trail(len(solution), self.current_alpha)
        else:
            c = np.full((len(solution), 4), (*self.base_colour, self.current_alpha))

        self.scatter.setData(color=c)
        self.line.setData(color=c)

    def _on_lyapunov_result(self, lyap, ky_dim, t_hist, lyap_hist):
        self.lyapunov_label.setText(
            f"λ = ({lyap[0]:+.2f}, {lyap[1]:+.2f}, {lyap[2]:+.2f})  D_KY = {ky_dim:.2f}"
        )

        self.lyapunov_container.setVisible(True)
        self.curve_l1.setData(t_hist, lyap_hist[:, 0])
        self.curve_l2.setData(t_hist, lyap_hist[:, 1])
        self.curve_l3.setData(t_hist, lyap_hist[:, 2])

    def _open_bifurcation(self):
        config = ATTRACTORS[self.current_name]
        values = {p.name: p.step * s.value() for p, s, _ in self.slider_rows}
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
