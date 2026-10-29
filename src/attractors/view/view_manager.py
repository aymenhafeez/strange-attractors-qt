# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import math

import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets

from ..core.signal_analysis import sample_times
from ..ui.style import PANEL_SURFACE, plot_colours
from .animation_controller import AnimationController
from .camera_controller import CameraController
from .grid_overlay import GridOverlay
from .particle_renderer import ParticleFlowRenderer
from .point_hover import PointHover
from .projection_emitter import ProjectionEmitter
from .trajectory_renderer import TrajectoryRenderer
from .viewport_overlay import ViewportOverlay


class ViewManager(QtCore.QObject):
    animation_finished = QtCore.pyqtSignal()
    animation_segments_data = QtCore.pyqtSignal(object)
    projections_data = QtCore.pyqtSignal(object, object, object)
    playback_range_changed = QtCore.pyqtSignal(float, float)
    playback_time_changed = QtCore.pyqtSignal(float)
    animation_state_changed = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._animation_mode = "trajectory"
        self._playback_run = None
        self._playback_times = ()
        self._playback_start = 0.0
        self._playback_end = 0.0
        self._playback_dt = 1.0
        self._playback_frames = 0

        self.container = QtWidgets.QWidget()
        self.container.setObjectName("panelSurface")
        self.container.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.container.setStyleSheet(PANEL_SURFACE)
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
            lambda: (
                self.animation_controller.is_active()
                or self.animation_controller.frame > 0
                and self._animation_mode == "trajectory"
            ),
        )

        self.particle_renderer = ParticleFlowRenderer(
            self.view, self.trajectory_renderer.get_particle_colours
        )

        self.animation_controller = AnimationController(
            self._render_animation_frame,
            self._sync_animation_visibility,
            self.animation_finished.emit,
            parent=self,
        )

        self.point_hover = PointHover(
            self.view,
            lambda: (
                self.trajectory_renderer.displayed_points()
                if not self.animation_controller.is_active()
                else []
            ),
            parent=self,
        )

    @property
    def grid_half_size(self):
        return self.grid_overlay.grid_half_size

    @property
    def grid_items(self):
        return self.grid_overlay.grid_items

    @property
    def animation_mode(self):
        return self._animation_mode

    def set_playback_source(self, run):
        if run is self._playback_run:
            return

        self.animation_controller.stop()
        self.animation_controller.reset_frame()
        self.trajectory_renderer.reset_animation()
        self._playback_run = run
        self._playback_times = ()

        if run is not None:
            self._playback_start = run["t_min"]
            self._playback_times = tuple(
                sample_times(run["t_min"], spec["t_max"], len(solution))
                for spec, solution in zip(
                    run["trajectory_specs"], run["solutions"], strict=True
                )
            )
            first = run["trajectory_specs"][0]
            self._playback_dt = (first["t_max"] - run["t_min"]) / len(
                run["solutions"][0]
            )
            self._playback_end = max(spec["t_max"] for spec in run["trajectory_specs"])
            self._playback_frames = math.ceil(
                (self._playback_end - self._playback_start) / self._playback_dt
            )

            if self._animation_mode == "trajectory":
                self.animation_controller.reset_frame(
                    self._playback_frames,
                    finished=True,
                )

        self._sync_playback_range()
        self._sync_animation_visibility()

    def _sync_playback_range(self):
        if not self._playback_times or self._animation_mode != "trajectory":
            self.playback_range_changed.emit(0.0, 0.0)
            return

        start = float(self._playback_times[0][0])
        self.playback_range_changed.emit(start, self._playback_end)
        time = min(
            self._playback_start + self.animation_controller.frame * self._playback_dt,
            self._playback_end,
        )
        self.playback_time_changed.emit(max(start, time))

    def seek_time(self, time):
        if not self._playback_times or self._animation_mode != "trajectory":
            return

        frame = round((time - self._playback_start) / self._playback_dt)
        self.animation_controller.seek(min(max(frame, 1), self._playback_frames))

    def set_animation_mode(self, mode):
        self.point_hover.clear()
        if mode not in {"trajectory", "particle"}:
            raise ValueError(f"Unknown animation mode {mode}")

        if mode == self._animation_mode:
            return

        self.animation_controller.stop()
        self.animation_controller.reset_frame()

        self._animation_mode = mode

        if mode == "trajectory" and self._playback_times:
            self.animation_controller.reset_frame(self._playback_frames, finished=True)
            self.trajectory_renderer.reset_animation()

        self.particle_renderer.set_visible(False)
        self.trajectory_renderer.update_display()
        self._sync_animation_visibility()
        self._sync_playback_range()

    def set_particle_count(self, value):
        self.particle_renderer.set_particle_count(value)

    def set_particle_trail_length(self, value):
        self.particle_renderer.set_trail_length(value)

    def _sync_animation_visibility(self):
        active = self.animation_controller.is_active()
        self.animation_state_changed.emit(active)
        particle_flow_active = active and self._animation_mode == "particle"

        self.trajectory_renderer.sync_head_visibility()

        if particle_flow_active:
            solutions = self.trajectory_renderer.solutions or []
            self.particle_renderer.render_frame(
                solutions, self.animation_controller.frame
            )

        self.particle_renderer.set_visible(particle_flow_active)

    def _sync_colourbar(self):
        renderer = self.trajectory_renderer
        self.viewport_overlay.colourbar.set_scale(
            renderer.colour_mode, renderer.colourmap, renderer.colour_limits
        )

    def set_colour_mode(self, mode):
        self.trajectory_renderer.set_colour_mode(mode)
        self._sync_colourbar()

    def set_colourmap(self, cmap):
        self.trajectory_renderer.set_colourmap(cmap)
        self._sync_colourbar()

    def display_solutions(self, solutions, is_partial):
        self.point_hover.clear()
        self.trajectory_renderer.display_solutions(solutions, is_partial)
        self._sync_colourbar()

    def clear_solutions(self):
        self.point_hover.clear()
        self.set_playback_source(None)
        self.particle_renderer.clear()
        self.trajectory_renderer.clear_solutions()
        self._sync_colourbar()

    def _render_animation_frame(self, current_frame, step):
        self.point_hover.clear()
        solutions = self.trajectory_renderer.solutions
        if not solutions:
            return None

        if self._animation_mode == "particle":
            frame = current_frame + step
            self.particle_renderer.render_frame(solutions, frame)

            return {"frame": frame, "done": False}

        if not self._playback_times:
            return None

        frame = min(current_frame + step, self._playback_frames)
        time = min(
            self._playback_start + frame * self._playback_dt,
            self._playback_end,
        )
        frames = [
            int(np.searchsorted(times, time, side="right"))
            for times in self._playback_times
        ]
        segments = self.trajectory_renderer.render_animation_frame(frames)

        self.animation_segments_data.emit(segments)
        self.projection_emitter.emit_segments(segments)
        self.playback_time_changed.emit(time)

        return {"frame": frame, "done": frame >= self._playback_frames}
