import numpy as np

from attractors.view_manager import _decimate_for_display, _decimate_indices


def test_decimate_indices_returns_none_for_short_arrays():
    assert _decimate_indices(5, 10) is None


def test_decimate_for_display_returns_short_arrays_unchanged():
    points = np.arange(15, dtype=np.float64).reshape(5, 3)

    decimated = _decimate_for_display(points, 10)

    assert decimated is points


def test_decimate_for_display_caps_long_arrays():
    points = np.arange(300, dtype=np.float64).reshape(100, 3)

    decimated = _decimate_for_display(points, 10)

    assert decimated.shape == (10, 3)


def test_decimate_for_display_preserves_first_and_last_points():
    points = np.arange(300, dtype=np.float64).reshape(100, 3)

    decimated = _decimate_for_display(points, 10)

    np.testing.assert_allclose(decimated[0], points[0])
    np.testing.assert_allclose(decimated[-1], points[-1])
