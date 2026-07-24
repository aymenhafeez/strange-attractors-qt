import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets

from .camera_controller import CameraController
from .grid_overlay import GridOverlay
from .lyapunov_overlay import LyapunovOverlay
from .style import CONTAINER, EQUATION_LABEL


N_BINS = 96
STATIC_RENDER_MAX_POINTS = 80000
ANIM_RENDER_MAX_POINTS = 30000


def _decimate_indices(n_points, max_points):
    if n_points <= max_points:
        return None

    return np.linspace(0, n_points - 1, max_points, dtype=np.int64)


def _decimate_for_display(points, max_points):
    idx = _decimate_indices(len(points), max_points)
    if idx is None:
        return points

    return points[idx]


class ViewManager(QtCore.QObject):
    animation_finished = QtCore.pyqtSignal()
    projections_data = QtCore.pyqtSignal(object, object, object)

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
        self._traj_tail_length = 5000
        self._traj_tail_enabled = False
        self._anim_step = 100
        self._colour_cache = {}

        self.container = QtWidgets.QWidget()
        self.container.setStyleSheet(CONTAINER)
        container_layout = QtWidgets.QGridLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.view = gl.GLViewWidget()
        self.camera_controller = CameraController(self.view, self)
        self.grid_overlay = GridOverlay(self.view)
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

        self.lyapunov_overlay = LyapunovOverlay(container_layout)

        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._animate_frame)

    def get_solutions(self):
        return self._solutions

    @property
    def grid_half_size(self):
        return self.grid_overlay.grid_half_size

    @property
    def grid_items(self):
        return self.grid_overlay.grid_items

    def reposition_overlays(self):
        if self._repositioning:
            return
        self._repositioning = True
        margin = 8
        self.view.lower()
        self._repositioning = False

    def build_grid(self, half_size):
        self.grid_overlay.build_grid(half_size)

    def set_grid_visible(self, visible):
        self.grid_overlay.set_grid_visible(visible)

    def set_poincare_plane(self, axis, value):
        self.grid_overlay.set_poincare_plane(axis, value)

    def remove_poincare_plane(self):
        self.grid_overlay.remove_poincare_plane()

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

    def set_alpha(self, val):
        self._current_alpha = val / 100.0 if val > 1 else val
        self.refresh_colours()

    def set_anim_step(self, step):
        self._anim_step = max(1, int(step))

    def set_orbit_mode(self, enabled):
        self.camera_controller.set_orbit_mode(enabled)

    def set_orbit_speed(self, speed):
        self.camera_controller.set_orbit_speed(speed)

    def _orbit_frame(self):
        self.camera_controller._orbit_frame()

    def set_trajectories(self, trajectories):
        self._trajectories = trajectories

    def set_info(self, config, values):
        formatted_params = "  ".join(f"{k}: {v:.2f}" for k, v in sorted(values.items()))
        equations = config.equation_text.replace("\n", "<br>")
        text = (
            f"<b>SYSTEM</b>: {config.name}<br>"
            f"{equations}<br>"
            f"<b>IC</b>: {config.initial_conditions}<br>"
            f"<b>PARAMS</b>: {formatted_params}"
        )
        self.equation_label.setText(text)
        self.equation_label.setVisible(True)
        self.equation_label.setToolTip(config.description)

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

    def _get_colour_array(self, n, alpha, base_colour):
        mode = "trail" if self._trail_mode else "flat"
        colour_key = tuple(round(float(c), 6) for c in base_colour)
        key = (mode, n, round(float(alpha), 6), colour_key)
        cached = self._colour_cache.get(key)
        if cached is not None:
            return cached

        if self._trail_mode:
            colour = self._plot_trail(n, alpha, base_colour)
        else:
            colour = np.full((n, 4), (*base_colour, alpha))

        self._colour_cache[key] = colour

        return colour

    def refresh_colours(self):
        if not self._solutions:
            return
        for i, sol in enumerate(self._solutions):
            if i >= len(self._scatters):
                break
            _, c = self._get_traj_tail_data(i, sol)
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
            segment, c = self._get_traj_tail_data(i, sol)
            self._scatters[i].setData(pos=segment, color=c)
            self._scatters[i].setVisible(not self._line_mode)
            self._lines[i].setData(pos=segment, color=c)
            self._lines[i].setVisible(self._line_mode)
            if i < len(self._heads):
                self._heads[i].setData(pos=segment[-1:], color=c[-1:])

    def auto_adjust_grid(self, solutions):
        self.grid_overlay.auto_adjust_grid(solutions)

    def set_camera(self, config):
        self.camera_controller.set_camera(config)

    def get_camera_state(self):
        return self.camera_controller.get_camera_state()

    def set_camera_state(self, state):
        return self.camera_controller.set_camera_state(state)

    def fit_camera_to_solutions(self):
        self.camera_controller.fit_camera_to_solutions(self._solutions)

    def set_lyapunov_result(self, lyap, ky_dim, t_hist, lyap_hist):
        self.lyapunov_overlay.set_result(lyap, ky_dim, t_hist, lyap_hist)

    def clear_lyapunov(self):
        self.lyapunov_overlay.clear()

    def save_view_as_png(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.container, "Save View as PNG", "", "PNG Files (*.png)"
        )
        if not filename:
            return

        img = self.view.grabFramebuffer()
        img.save(filename)

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

    def _get_traj_tail_data(self, i, sol):
        if self._traj_tail_enabled:
            segment = sol[-self._traj_tail_length :]
        else:
            segment = sol

        segment = _decimate_for_display(segment, STATIC_RENDER_MAX_POINTS)

        base_colour, alpha = self._get_traj_colour_alpha(i)
        c = self._get_colour_array(len(segment), alpha, base_colour)

        return segment, c

    def set_trail_mode(self, checked):
        self._trail_mode = checked
        self._traj_tail_enabled = checked
        self._update_display()

    def set_traj_tail_length(self, val):
        self._traj_tail_length = val
        self._update_display()

    def _update_display(self):
        if not self._solutions:
            return
        for i, sol in enumerate(self._solutions):
            if i >= len(self._scatters):
                break
            segment, c = self._get_traj_tail_data(i, sol)
            self._scatters[i].setData(pos=segment, color=c)
            self._scatters[i].setVisible(not self._line_mode)
            self._lines[i].setData(pos=segment, color=c)
            self._lines[i].setVisible(self._line_mode)
            if i < len(self._heads):
                self._heads[i].setData(pos=segment[-1:], color=c[-1:])

    def _animate_frame(self):
        if not self._solutions:
            return

        sol0 = self._solutions[0]
        frame = min(self._anim_frame + self._anim_step, len(sol0))
        self._anim_frame = frame

        all_segments = []
        for i, sol in enumerate(self._solutions):
            if self._traj_tail_enabled:
                start = max(0, frame - self._traj_tail_length)
                segment = sol[start:frame]
            else:
                segment = sol[:frame]
            render_segment = _decimate_for_display(segment, ANIM_RENDER_MAX_POINTS)
            base_colour, alpha = self._get_traj_colour_alpha(i)
            c = self._get_colour_array(len(render_segment), alpha, base_colour)
            if i < len(self._scatters):
                self._scatters[i].setData(pos=render_segment, color=c)
                self._lines[i].setData(pos=render_segment, color=c)
            if i < len(self._heads):
                self._heads[i].setData(pos=render_segment[-1:], color=c[-1:])
            all_segments.append(segment)

        if all_segments:
            all_pts = np.concatenate(all_segments, axis=0)
            finite = np.all(np.isfinite(all_pts), axis=1)
            if np.any(finite):
                x, y, z = all_pts[finite].T
                self.projections_data.emit(x, y, z)

        if frame >= len(sol0):
            self._timer.stop()
            self._sync_head_visibility()
            self.animation_finished.emit()
