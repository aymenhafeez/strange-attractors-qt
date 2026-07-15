import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .custom_panel import CustomPanel
from .style import (
    CONTAINER,
    EQUATION_LABEL,
    LYAPUNOV_PLOT,
    STATUS_BAR,
    STATUS_IC,
    STATUS_PARAMS,
    STATUS_SYSTEM,
)
from .trajectory_panel import TrajectoryPanel


N_BINS = 96


class ViewManager(QtCore.QObject):
    animation_finished = QtCore.pyqtSignal()
    trajectories_changed = QtCore.pyqtSignal(list)
    styles_changed = QtCore.pyqtSignal(list)
    projections_data = QtCore.pyqtSignal(object, object, object)
    custom_compiled = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._solutions = None
        self._scatters = []
        self._lines = []
        self._trajectories = []
        self._base_colour = (1.0, 1.0, 1.0)
        self._current_alpha = 1.0
        self._line_mode = False
        self._trail_mode = False
        self._heads = []
        self._heads_visible = True
        self._repositioning = False
        self._anim_frame = 0
        self._anim_step = 200
        self._grid_visible = True
        self.grid_half_size = 30.0
        self.grid_items = []

        self.container = QtWidgets.QWidget()
        self.container.setStyleSheet(CONTAINER)
        container_layout = QtWidgets.QGridLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.view = gl.GLViewWidget()
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

        self.status_system = QtWidgets.QLabel("")
        self.status_params = QtWidgets.QLabel("")
        self.status_ic = QtWidgets.QLabel("")

        status_container = QtWidgets.QWidget()
        status_container.setStyleSheet(STATUS_BAR)
        status_layout = QtWidgets.QHBoxLayout(status_container)
        status_layout.setContentsMargins(1, 0, 8, 0)
        status_layout.setSpacing(0)
        for lbl in [self.status_system, self.status_params, self.status_ic]:
            lbl.setStyleSheet(STATUS_PARAMS)
            status_layout.addWidget(lbl)
        status_container.setFixedHeight(22)
        container_layout.addWidget(status_container, 1, 0)
        self.status_system.setStyleSheet(STATUS_SYSTEM)
        self.status_ic.setStyleSheet(STATUS_IC)

        self.custom_panel = CustomPanel(self.container)
        self.custom_panel.compile_requested.connect(self._on_custom_compiled)
        self.custom_panel.setVisible(False)
        self.custom_panel.raise_()

        self.trajectory_panel = TrajectoryPanel(self.container)
        self.trajectory_panel.trajectories_changed.connect(
            self._on_trajectories_changed
        )
        self.trajectory_panel.styles_changed.connect(self._on_styles_changed)
        self.trajectory_panel.raise_()

        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._animate_frame)

    def _on_custom_compiled(self, config):
        self.custom_compiled.emit(config)

    def _on_trajectories_changed(self, trajectories):
        self._trajectories = trajectories
        self.trajectories_changed.emit(trajectories)

    def _on_styles_changed(self, trajectories):
        self._trajectories = trajectories
        self.styles_changed.emit(trajectories)

    def get_solutions(self):
        return self._solutions

    def get_trajectories(self):
        return self._trajectories

    def reposition_overlays(self):
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

    def build_grid(self, half_size):
        for item in self.grid_items:
            self.view.removeItem(item)
        self.grid_items.clear()

        is_visible = self._grid_visible

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

    def set_grid_visible(self, visible):
        self._grid_visible = visible
        for item in self.grid_items:
            item.setVisible(visible)

    def sync_gl_items(self, n):
        while len(self._scatters) < n:
            scatter = gl.GLScatterPlotItem(size=1.0)
            scatter.setGLOptions("additive")
            scatter.setVisible(not self._line_mode)
            self.view.addItem(scatter)
            self._scatters.append(scatter)
            line = gl.GLLinePlotItem()
            line.setVisible(self._line_mode)
            self.view.addItem(line)
            self._lines.append(line)
        while len(self._scatters) > n:
            self.view.removeItem(self._scatters.pop())
            self.view.removeItem(self._lines.pop())
        while len(self._heads) < n:
            head = gl.GLScatterPlotItem(size=20.0)
            head.setGLOptions("additive")
            self.view.addItem(head)
            self._heads.append(head)
        while len(self._heads) > n:
            self.view.removeItem(self._heads.pop())
        self._sync_head_visibility()

    def set_line_mode(self, checked):
        self._line_mode = checked
        for scatter, line in zip(self._scatters, self._lines):
            line.setVisible(checked)
            scatter.setVisible(not checked)

    def set_point_mode(self, checked):
        self._heads_visible = checked
        self._sync_head_visibility()

    def _sync_head_visibility(self):
        visible = self._heads_visible and self._timer.isActive()
        for h in self._heads:
            h.setVisible(visible)

    def set_trail_mode(self, checked):
        self._trail_mode = checked
        self.refresh_colours()

    def set_alpha(self, val):
        self._current_alpha = val / 100.0 if val > 1 else val
        self.refresh_colours()

    def set_trajectories(self, trajectories):
        self._trajectories = trajectories

    def update_status(self, config, values):
        formatted_params = "  ".join(
            f"{k}: {v:.2f}" for k, v in sorted(values.items())
        )
        self.status_system.setText(f"<b>SYSTEM</b>: {config.name}")
        self.status_system.setToolTip(f"{config.description}")
        self.status_params.setText(f"<b>PARAMS</b>: {formatted_params}")
        self.status_ic.setText(f"<b>IC</b>: {config.initial_conditions}")

    def _get_traj_colour_alpha(self, i):
        traj = self._trajectories[i] if i < len(self._trajectories) else None
        if traj is not None:
            qc = traj["colour"]
            base_colour = (qc.redF(), qc.greenF(), qc.blueF())
            alpha = self._current_alpha * traj.get("alpha", 1.0)
        else:
            base_colour = self._base_colour
            alpha = self._current_alpha
        return base_colour, alpha

    def _plot_trail(self, n, alpha=1.0, base_colour=None):
        if base_colour is None:
            base_colour = self._base_colour
        colour = np.zeros((n, 4))
        colour[:, 0] = np.linspace(0.2, base_colour[0], n)
        colour[:, 1] = np.linspace(0.2, base_colour[1], n)
        colour[:, 2] = np.linspace(0.5, base_colour[2], n)
        colour[:, 3] = np.linspace(0.0, alpha, n)
        return colour

    def refresh_colours(self):
        if not self._solutions:
            return
        for i, sol in enumerate(self._solutions):
            if i >= len(self._scatters):
                break
            base_colour, alpha = self._get_traj_colour_alpha(i)
            if self._trail_mode:
                c = self._plot_trail(len(sol), alpha, base_colour)
            else:
                c = np.full((len(sol), 4), (*base_colour, alpha))
            self._scatters[i].setData(color=c)
            self._scatters[i].setVisible(not self._line_mode)
            self._lines[i].setData(color=c)
            self._lines[i].setVisible(self._line_mode)
            if i < len(self._heads):
                self._heads[i].setData(color=c[-1:])

    def display_solutions(self, solutions, is_partial):
        if not is_partial:
            self._solutions = solutions

        self.sync_gl_items(len(solutions))

        for i, sol in enumerate(solutions):
            base_colour, alpha = self._get_traj_colour_alpha(i)
            if self._trail_mode:
                c = self._plot_trail(len(sol), alpha, base_colour)
            else:
                c = np.full((len(sol), 4), (*base_colour, alpha))
            self._scatters[i].setData(pos=sol, color=c)
            self._scatters[i].setVisible(not self._line_mode)
            self._lines[i].setData(pos=sol, color=c)
            self._lines[i].setVisible(self._line_mode)
            if i < len(self._heads):
                self._heads[i].setData(pos=sol[-1:], color=c[-1:])

    def auto_adjust_grid(self, solutions):
        if not solutions:
            return
        new_half = min(float(np.max(np.abs(solutions[0]))) * 3, 500.0)
        if (
            abs(new_half - self.grid_half_size) / max(self.grid_half_size, 1e-6)
            > 0.1
        ):
            self.build_grid(new_half)

    def set_equation(self, text):
        self.equation_label.setText(text)
        self.equation_label.setVisible(bool(text))

    def set_camera(self, config):
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

    def set_lyapunov_result(self, lyap, ky_dim, t_hist, lyap_hist):
        self.lyapunov_label.setText(
            f"\u03bb = ({lyap[0]:+.2f}, {lyap[1]:+.2f}, {lyap[2]:+.2f})  D_KY = {ky_dim:.2f}"
        )
        self.lyapunov_container.setVisible(True)
        self.curve_l1.setData(t_hist, lyap_hist[:, 0])
        self.curve_l2.setData(t_hist, lyap_hist[:, 1])
        self.curve_l3.setData(t_hist, lyap_hist[:, 2])

    def clear_lyapunov(self):
        self.lyapunov_label.setText("")
        self.lyapunov_container.setVisible(False)

    def reset_trajectory_panel(self, config):
        self.trajectory_panel.reset(config)

    def toggle_animation(self):
        if self._timer.isActive():
            self._timer.stop()
            self._sync_head_visibility()
            return False
        else:
            self._anim_frame = 0
            self._timer.start(16)
            self._sync_head_visibility()
            return True

    def stop_animation(self):
        self._timer.stop()

    def is_animating(self):
        return self._timer.isActive()

    def _animate_frame(self):
        if not self._solutions:
            return

        sol0 = self._solutions[0]
        frame = min(self._anim_frame + self._anim_step, len(sol0))
        self._anim_frame = frame

        all_segments = []
        for i, sol in enumerate(self._solutions):
            segment = sol[:frame]
            base_colour, alpha = self._get_traj_colour_alpha(i)
            if self._trail_mode:
                c = self._plot_trail(len(segment), alpha, base_colour)
            else:
                c = np.full((len(segment), 4), (*base_colour, alpha))
            if i < len(self._scatters):
                self._scatters[i].setData(pos=segment, color=c)
                self._lines[i].setData(pos=segment, color=c)
            if i < len(self._heads):
                self._heads[i].setData(pos=segment[-1:], color=c[-1:])
            all_segments.append(segment)

        if all_segments:
            all_pts = np.concatenate(all_segments, axis=0)
            x, y, z = all_pts.T
            self.projections_data.emit(x, y, z)

        if frame >= len(sol0):
            self._timer.stop()
            self._sync_head_visibility()
            self.animation_finished.emit()

        if frame >= len(sol0):
            self._timer.stop()
            self.animation_finished.emit()
