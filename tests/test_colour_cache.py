from types import SimpleNamespace

import numpy as np
import pytest

from attractors.view_manager import ViewManager


def _manager(trail_mode=False):
    manager = SimpleNamespace(
        _trail_mode=trail_mode,
        _base_colour=(1.0, 1.0, 1.0),
        _colour_cache={},
    )
    manager._plot_trail = lambda n, alpha, base_colour: ViewManager._plot_trail(
        manager, n, alpha, base_colour
    )
    return manager


def test_colour_cache_builds_flat_colour_array():
    manager = _manager()

    colour = ViewManager._get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))

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

    first = ViewManager._get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))
    second = ViewManager._get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))

    assert second is first


def test_colour_cache_separates_different_alpha_values():
    manager = _manager()

    first = ViewManager._get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))
    second = ViewManager._get_colour_array(manager, 3, 0.75, (0.1, 0.2, 0.3))

    assert second is not first
    assert second[0, 3] == pytest.approx(0.75)


def test_colour_cache_separates_flat_and_trail_modes():
    manager = _manager()

    flat = ViewManager._get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))
    manager._trail_mode = True
    trail = ViewManager._get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))

    assert trail is not flat
    assert trail[0, 3] == pytest.approx(0.0)
    assert trail[-1, 3] == pytest.approx(0.5)


def test_colour_cache_reuses_matching_trail_array():
    manager = _manager(trail_mode=True)

    first = ViewManager._get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))
    second = ViewManager._get_colour_array(manager, 3, 0.5, (0.1, 0.2, 0.3))

    assert second is first
