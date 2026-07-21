import numpy as np
import pytest

from attractors.poincare_panel import compute_poincare_crossings


def test_returns_empty_arrays_when_no_crossings():
    sol = np.array(
        [
            [0.0, 10.0, 100.0],
            [1.0, 20.0, 200.0],
            [2.0, 30.0, 300.0],
        ],
        dtype=np.float64,
    )

    h, v = compute_poincare_crossings(sol, "x", 10.0)

    assert h.shape == (0,)
    assert v.shape == (0,)


def test_rising_crossing_interpolates_plane_x_to_yz():
    sol = np.array(
        [
            [-1.0, 10.0, 100.0],
            [1.0, 20.0, 200.0],
        ],
        dtype=np.float64,
    )

    h, v = compute_poincare_crossings(sol, "x", 0.0, direction="positive")

    assert h == pytest.approx([15.0])
    assert v == pytest.approx([150.0])


def test_falling_crossing_interpolates_plane_x_to_yz():
    sol = np.array(
        [
            [1.0, 20.0, 200.0],
            [-1.0, 10.0, 100.0],
        ],
        dtype=np.float64,
    )

    h, v = compute_poincare_crossings(sol, "x", 0.0, direction="negative")

    assert h == pytest.approx([15.0])
    assert v == pytest.approx([150.0])
