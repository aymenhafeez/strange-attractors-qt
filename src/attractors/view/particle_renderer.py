from dataclasses import dataclass

import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import OpenGLConstants as GLC

from ..ui.style import plot_colours

DEFAULT_PARTICLE_COUNT = 600
DEFAULT_TRAIL_LENGTH = 18
PARTICLE_HEAD_SIZE = 5.0
TRAIL_ALPHA_SCALE = 0.7

TRAIL_GL_OPTIONS_LIGHT = {
    GLC.GL_DEPTH_TEST: False,
    GLC.GL_BLEND: True,
    GLC.GL_CULL_FACE: False,
    "glBlendFuncSeparate": (
        GLC.GL_SRC_ALPHA,
        GLC.GL_ONE_MINUS_SRC_ALPHA,
        GLC.GL_ONE,
        GLC.GL_ONE_MINUS_SRC_ALPHA,
    ),
}


@dataclass(frozen=True)
class ParticleGeometry:
    trail_positions: np.ndarray
    trail_colours: np.ndarray
    head_positions: np.ndarray
    head_colours: np.ndarray


def _empty_particle_geometry() -> ParticleGeometry:
    return ParticleGeometry(
        trail_positions=np.empty((0, 3)),
        trail_colours=np.empty((0, 4)),
        head_positions=np.empty((0, 3)),
        head_colours=np.empty((0, 4)),
    )


def allocate_particle_count(solutions, total_count):
    lengths = np.asarray([len(solution) for solution in solutions])
    counts = np.zeros(len(lengths))

    total_counts = max(0, int(total_count))
    usable = np.flatnonzero(lengths >= 2)

    if total_count == 0 or len(usable) == 0:
        return counts

    if total_count < len(usable):
        counts[usable[:total_counts]] = 1
        return counts

    counts[usable] = 1
    remaining = total_counts - len(usable)

    if remaining == 0:
        return counts

    weights = lengths[usable] / lengths[usable].sum()
    shares = weights * remaining
    extras = np.floor(shares).astype(np.int64)
    counts[usable] += extras

    leftover = remaining - int(extras.sum())
    if leftover:
        fractions = shares - extras
        order = np.argsort(-fractions, kind="stable")
        counts[usable[order[:leftover]]] += 1

    return counts


def build_particle_geometry(points, point_colours, particle_count, trail_length, phase):
    points = np.asarray(points)
    point_colours = np.asarray(point_colours)

    if point_colours.shape != (len(points), 4):
        raise ValueError("Point colours must have shape (N, 4)")

    if len(points) < 2 or particle_count <= 0:
        return _empty_particle_geometry()

    particle_count = min(int(particle_count), len(points))
    trail_length = min(max(2, int(trail_length)), len(points))

    head_indices = np.floor(
        np.linspace(0, len(points), particle_count, endpoint=False) + phase
    ).astype(np.int64) % len(points)

    offsets = np.arange(trail_length - 1, -1, -1)
    indices = (head_indices[:, None] - offsets[None, :]) % len(points)

    starts = indices[:, :-1]
    ends = indices[:, 1:]
    valid_segments = ends == starts + 1

    pairs = np.stack((starts[valid_segments], ends[valid_segments]), axis=1).reshape(-1)

    trail_positions = points[pairs]
    trail_colours = point_colours[pairs].copy()

    fade = np.linspace(0.0, TRAIL_ALPHA_SCALE, trail_length)

    start_fade = np.broadcast_to(
        fade[:-1],
        starts.shape,
    )[valid_segments]
    end_fade = np.broadcast_to(
        fade[1:],
        ends.shape,
    )[valid_segments]

    trail_fade = np.stack(
        (start_fade, end_fade),
        axis=1,
    ).reshape(-1)

    trail_colours[:, 3] *= trail_fade

    head_positions = points[head_indices]
    head_colours = point_colours[head_indices].copy()

    return ParticleGeometry(
        trail_positions, trail_colours, head_positions, head_colours
    )


class ParticleFlowRenderer:
    def __init__(self, view, colour_provider):
        self.view = view
        self._colour_provider = colour_provider
        self._particle_count = DEFAULT_PARTICLE_COUNT
        self._trail_length = DEFAULT_TRAIL_LENGTH
        self._visible = False
        self._trails = []
        self._heads = []

    def _gl_options(self):
        if plot_colours()["is_dark"]:
            return "additive"
        return TRAIL_GL_OPTIONS_LIGHT

    def set_particle_count(self, value):
        self._particle_count = max(1, int(value))

    def set_trail_length(self, value):
        self._trail_length = max(2, int(value))

    def sync_gl_items(self, count):
        while len(self._trails) < count:
            trail = gl.GLLinePlotItem(mode="lines", width=1.0)
            trail.setGLOptions(self._gl_options())
            trail.setVisible(False)
            self.view.addItem(trail)
            self._trails.append(trail)

            head = gl.GLScatterPlotItem(size=PARTICLE_HEAD_SIZE, pxMode=True)
            head.setGLOptions(self._gl_options())
            head.setVisible(False)
            self.view.addItem(head)
            self._heads.append(head)

        while len(self._trails) > count:
            self.view.removeItem(self._trails.pop())
            self.view.removeItem(self._heads.pop())

    def render_frame(self, solutions, phase):
        self.sync_gl_items(len(solutions))

        particle_counts = allocate_particle_count(solutions, self._particle_count)

        for i, (solution, count) in enumerate(zip(solutions, particle_counts)):
            point_colours = self._colour_provider(i)

            geometry = build_particle_geometry(
                solution, point_colours, count, self._trail_length, phase
            )

            trail = self._trails[i]
            head = self._heads[i]

            trail.setData(
                pos=geometry.trail_positions,
                color=geometry.trail_colours,
                width=1.0,
                mode="lines",
            )
            head.setData(
                pos=geometry.head_positions,
                color=geometry.head_colours,
                size=PARTICLE_HEAD_SIZE,
                pxMode=True,
            )

            trail.setVisible(self._visible and len(geometry.trail_positions) > 0)
            head.setVisible(self._visible and len(geometry.head_positions) > 0)

    def set_visible(self, visible):
        self._visible = visible

        for trail in self._trails:
            trail.setVisible(visible)

        for head in self._heads:
            head.setVisible(visible)

    def clear(self):
        self.sync_gl_items(0)

    def apply_theme(self):
        gl_options = self._gl_options()

        for trail in self._trails:
            trail.setGLOptions(gl_options)

        for head in self._heads:
            head.setGLOptions(gl_options)
