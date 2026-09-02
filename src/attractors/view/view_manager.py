import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets

from ..ui.style import plot_colours
from .animation_controller import AnimationController
from .camera_controller import CameraController
from .grid_overlay import GridOverlay
from .projection_emitter import ProjectionEmitter
from .trajectory_renderer import TrajectoryRenderer
from .viewport_overlay import ViewportOverlay


class ViewManager(QtCore.QObject):
    animation_finished = QtCore.pyqtSignal()
    animation_segments_data = QtCore.pyqtSignal(object)
    projections_data = QtCore.pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._repositioning = False

        self.container = QtWidgets.QWidget()
        self.container.setObjectName("viewportContainer")
        self.container.setStyleSheet("""
            QWidget#viewportContainer {
                border: 1px solid palette(mid);
            }
        """)
        container_layout = QtWidgets.QGridLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor(plot_colours()["gl_background"])

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

        self.trajectory_renderer = TrajectoryRenderer(
            self.view,
            lambda: self.animation_controller.is_active(),
        )
        self.animation_controller = AnimationController(
            self._render_animation_frame,
            self.trajectory_renderer.sync_head_visibility,
            self.animation_finished.emit,
            parent=self,
        )

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

    def clear_solutions(self):
        self.animation_controller.reset_frame()
        self.trajectory_renderer.clear_solutions()

    def _render_animation_frame(self, current_frame, step):
        solutions = self.trajectory_renderer.solutions
        if not solutions:
            return None

        sol0 = solutions[0]
        frame = min(current_frame + step, len(sol0))

        all_segments = self.trajectory_renderer.render_animation_frame(frame)

        self.animation_segments_data.emit(all_segments)
        self.projection_emitter.emit_segments(all_segments)

        return {"frame": frame, "done": frame >= len(sol0)}
