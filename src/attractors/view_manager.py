import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets

from .camera_controller import CameraController
from .grid_overlay import GridOverlay
from .lyapunov_overlay import LyapunovOverlay
from .style import CONTAINER, EQUATION_LABEL
from .trajectory_renderer import TrajectoryRenderer


N_BINS = 96


class ViewManager(QtCore.QObject):
    animation_finished = QtCore.pyqtSignal()
    projections_data = QtCore.pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._repositioning = False
        self._anim_frame = 0
        self._anim_step = 100

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
        self.trajectory_renderer = TrajectoryRenderer(
            self.view,
            self._timer.isActive,
        )

    def get_solutions(self):
        return self.trajectory_renderer.solutions

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
        self.trajectory_renderer.sync_gl_items(n)

    def set_line_mode(self, checked):
        self.trajectory_renderer.set_line_mode(checked)

    def set_point_mode(self, checked):
        self.trajectory_renderer.set_point_mode(checked)

    def _sync_head_visibility(self):
        self.trajectory_renderer.sync_head_visibility()

    def set_alpha(self, val):
        self.trajectory_renderer.set_alpha(val)

    def set_anim_step(self, step):
        self._anim_step = max(1, int(step))

    def set_orbit_mode(self, enabled):
        self.camera_controller.set_orbit_mode(enabled)

    def set_orbit_speed(self, speed):
        self.camera_controller.set_orbit_speed(speed)

    def _orbit_frame(self):
        self.camera_controller._orbit_frame()

    def set_trajectories(self, trajectories):
        self.trajectory_renderer.set_trajectories(trajectories)

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
        return self.trajectory_renderer.get_traj_colour_alpha(i)

    def _plot_trail(self, n, alpha=1.0, base_colour=None):
        return self.trajectory_renderer.plot_trail(n, alpha, base_colour)

    def _get_colour_array(self, n, alpha, base_colour):
        return self.trajectory_renderer.get_colour_array(n, alpha, base_colour)

    def refresh_colours(self):
        self.trajectory_renderer.refresh_colours()

    def display_solutions(self, solutions, is_partial):
        self.trajectory_renderer.display_solutions(solutions, is_partial)

    def clear_solutions(self):
        self._anim_frame = 0
        self.trajectory_renderer.clear_solutions()

    def auto_adjust_grid(self, solutions):
        self.grid_overlay.auto_adjust_grid(solutions)

    def set_camera(self, config):
        self.camera_controller.set_camera(config)

    def get_camera_state(self):
        return self.camera_controller.get_camera_state()

    def set_camera_state(self, state):
        return self.camera_controller.set_camera_state(state)

    def fit_camera_to_solutions(self):
        self.camera_controller.fit_camera_to_solutions(self.get_solutions())

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
        return self.trajectory_renderer.get_traj_tail_data(i, sol)

    def set_trail_mode(self, checked):
        self.trajectory_renderer.set_trail_mode(checked)

    def set_traj_tail_length(self, val):
        self.trajectory_renderer.set_traj_tail_length(val)

    def _update_display(self):
        self.trajectory_renderer.update_display()

    def _animate_frame(self):
        solutions = self.get_solutions()
        if not solutions:
            return

        sol0 = solutions[0]
        frame = min(self._anim_frame + self._anim_step, len(sol0))
        self._anim_frame = frame

        all_segments = self.trajectory_renderer.render_animation_frame(frame)

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
