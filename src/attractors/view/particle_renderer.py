from dataclasses import dataclass

import numpy as np
import pyqtgraph.opengl as gl

DEFAULT_PARTICAL_COUNT = 600
DEFAULT_TRAIL_LENGTH = 18
PARTICLE_HEAD_SIZE = 4.0
TRAIL_ALPHA_SCALE = 0.7


@dataclass(frozen=True)
class ParticleGeometry:
    trail_position: np.ndarray
    trail_colours: np.ndarray
    head_position: np.ndarray
    head_colours: np.ndarray


def allocate_particle_count(solutions, total_count):
    pass


def build_particle_geometry(
    points, particle_count, trail_length, phase, base_colour, alpha
):
    points = np.asarray(points)
    particle_count = min(int(particle_count), len(points))
    trail_length = min(max(2, int(trail_length)), len(points))

    head_indices = np.floor(
        np.linspace(0, len(points), particle_count, endpoint=False) + phase
    ).astype(np.int64) % len(points)

    offsets = np.arange(trail_length - 1, -1, -1)
    indices = (head_indices[:, None] - offsets[None, :]) % len(points)

    starts = indices[:, -1]
    ends = indices[:, 1:]
    valid_segments = ends == starts + 1

    pairs = np.stack((starts[valid_segments], ends[valid_segments]), axis=1).reshape(-1)

    trail_positions = points[pairs]


class ParticleFlowRenderer:
    def __init__(self, view, colour_provider):
        self.view = view
        self._colour_provider = colour_provider
        self._particle_count = DEFAULT_PARTICAL_COUNT
        self._trail_length = DEFAULT_TRAIL_LENGTH
        self._visible = False
        self._trails = []
        self._heads = []
