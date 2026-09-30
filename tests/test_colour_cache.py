from types import SimpleNamespace

import numpy as np
import pytest

from attractors.view.trajectory_renderer import TrajectoryRenderer


def _manager(trail_mode=False):
    manager = SimpleNamespace(
        _trail_mode=trail_mode,
        _base_colour=(1.0, 1.0, 1.0),
        _colour_cache={},
    )
    manager.plot_trail = lambda n, alpha, base_colour: TrajectoryRenderer.plot_trail(
        manager, n, alpha, base_colour
    )
    return manager


def test_colour_cache_builds_flat_colour_array():
    manager = _manager()

    colour = TrajectoryRenderer.get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))

    assert colour.shape == (3, 4)
    np.testing.assert_allclose(
        colour,
        [
            [0.1, 0.2, 0.3, 0.5],
            [0.1, 0.2, 0.3, 0.5],
            [0.1, 0.2, 0.3, 0.5],
        ],
    )


def test_colour_cache_reuses_matching_flat_array():
    manager = _manager()

    first = TrajectoryRenderer.get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))
    second = TrajectoryRenderer.get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))

    assert second is first


def test_colour_cache_separates_different_alpha_values():
    manager = _manager()

    first = TrajectoryRenderer.get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))
    second = TrajectoryRenderer.get_colour_array(manager, 3, 0.75, (0.1, 0.2, 0.3))

    assert second is not first
    assert second[0, 3] == pytest.approx(0.75)
