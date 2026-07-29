import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .animation_controller import AnimationController
from .camera_controller import CameraController
from .grid_overlay import GridOverlay
from .projection_emitter import ProjectionEmitter
from .style import CONTAINER
from .trajectory_renderer import TrajectoryRenderer
from .viewport_overlay import ViewportOverlay

VIEWPORT_CORNER_RADIUS = 8


def _bottom_rounded_path(width, height, radius):
    radius = max(0, min(int(radius), int(width) // 2, int(height) // 2))
    if width <= 0 or height <= 0 or radius <= 0:
        return None

    right = float(width)
    bottom = float(height)
    radius = float(radius)

    path = QtGui.QPainterPath()
    path.moveTo(0.0, 0.0)
    path.lineTo(right, 0.0)
    path.lineTo(right, bottom - radius)
    path.arcTo(
        right - radius * 2.0,
        bottom - radius * 2.0,
        radius * 2.0,
        radius * 2.0,
        0.0,
        -90.0,
    )
    path.lineTo(radius, bottom)
    path.arcTo(
        0.0,
        bottom - radius * 2.0,
        radius * 2.0,
        radius * 2.0,
        270.0,
        -90.0,
    )
    path.lineTo(0.0, 0.0)
    path.closeSubpath()
    return path


def _bottom_rounded_mask(width, height, radius):
    path = _bottom_rounded_path(width, height, radius)
    if path is None:
        return None

    mask = QtGui.QBitmap(int(width), int(height))
    mask.fill(QtCore.Qt.GlobalColor.color0)
    painter = QtGui.QPainter(mask)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtCore.Qt.GlobalColor.color1)
    painter.drawPath(path)
    painter.end()

    return mask


class _BottomRoundedMaskMixin:
    def _init_bottom_rounded_mask(self, radius):
        self._corner_radius = int(radius)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_corner_mask()

    def _apply_corner_mask(self):
        mask = _bottom_rounded_mask(
            self.width(),
            self.height(),
            self._corner_radius,
        )
        if mask is None:
            self.clearMask()
            return
        self.setMask(mask)


class _RoundedViewportContainer(_BottomRoundedMaskMixin, QtWidgets.QWidget):
    def __init__(self, parent=None, *, radius=VIEWPORT_CORNER_RADIUS):
        super().__init__(parent)
        self._init_bottom_rounded_mask(radius)


class _RoundedGLViewWidget(_BottomRoundedMaskMixin, gl.GLViewWidget):
    def __init__(self, parent=None, *, radius=VIEWPORT_CORNER_RADIUS):
        super().__init__(parent)
        self._init_bottom_rounded_mask(radius)


class ViewManager(QtCore.QObject):
    animation_finished = QtCore.pyqtSignal()
    projections_data = QtCore.pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._repositioning = False

        self.container = _RoundedViewportContainer()
        self.container.setStyleSheet(CONTAINER)
        container_layout = QtWidgets.QGridLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.view = _RoundedGLViewWidget()
        self.camera_controller = CameraController(self.view, self)
        self.grid_overlay = GridOverlay(self.view)
        container_layout.addWidget(self.view, 0, 0)
        container_layout.setRowStretch(0, 1)
        container_layout.setColumnStretch(0, 1)

        self.viewport_overlay = ViewportOverlay(
            self.container,
            container_layout,
            self.view,
        )
        self.equation_label = self.viewport_overlay.equation_label

        self.projection_emitter = ProjectionEmitter(self.projections_data)

        self.animation_controller = AnimationController(
            self._render_animation_frame,
            self._sync_head_visibility,
            self.animation_finished.emit,
            parent=self,
        )
        self.trajectory_renderer = TrajectoryRenderer(
            self.view,
            self.animation_controller.is_active,
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
        self.animation_controller.set_step(step)

    def set_orbit_mode(self, enabled):
        self.camera_controller.set_orbit_mode(enabled)

    def set_orbit_speed(self, speed):
        self.camera_controller.set_orbit_speed(speed)

    def _orbit_frame(self):
        self.camera_controller._orbit_frame()

    def set_trajectories(self, trajectories):
        self.trajectory_renderer.set_trajectories(trajectories)

    def set_info(self, config, values):
        self.viewport_overlay.set_info(config, values)

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
        self.animation_controller.reset_frame()
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

    def save_view_as_png(self):
        return self.viewport_overlay.save_view_as_png()

    def toggle_animation(self):
        return self.animation_controller.toggle()

    def stop_animation(self):
        self.animation_controller.stop()

    def is_animating(self):
        return self.animation_controller.is_active()

    def set_loop_animation(self, checked):
        self.animation_controller.set_loop(checked)

    def _get_traj_tail_data(self, i, sol):
        return self.trajectory_renderer.get_traj_tail_data(i, sol)

    def set_trail_mode(self, checked):
        self.trajectory_renderer.set_trail_mode(checked)

    def set_traj_tail_length(self, val):
        self.trajectory_renderer.set_traj_tail_length(val)

    def _update_display(self):
        self.trajectory_renderer.update_display()

    def _render_animation_frame(self, current_frame, step):
        solutions = self.get_solutions()
        if not solutions:
            return None

        sol0 = solutions[0]
        frame = min(current_frame + step, len(sol0))

        all_segments = self.trajectory_renderer.render_animation_frame(frame)

        self.projection_emitter.emit_segments(all_segments)

        return {"frame": frame, "done": frame >= len(sol0)}

    def _animate_frame(self):
        self.animation_controller.advance()
