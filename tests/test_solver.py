import numba
import numpy as np
import pytest

from attractors.solver import solve_rk4


@numba.njit(nogil=True)
def _constant_system(state, t, params):
    return np.array([1.0, -2.0, 0.5])


@numba.njit(nogil=True)
def _exponential_x_system(state, t, params):
    x, y, z = state
    return np.array([x, 0.0, 0.0])
def test_solve_rk4_returns_expected_shape():
    y0 = np.array([0.0, 0.0, 0.0])
    params = np.array([], dtype=np.float64)

    sol = solve_rk4(_constant_system, y0, 0.0, 1.0, 10, params)

    assert sol.shape == (10, 3)
    assert sol.dtype == np.float64


def test_solve_rk4_integrates_simple_exponential():
    y0 = np.array([1.0, 0.0, 0.0])
    params = np.array([], dtype=np.float64)

    sol = solve_rk4(_exponential_x_system, y0, 0.0, 1.0, 1000, params)

    assert sol[-1, 0] == pytest.approx(np.e, rel=1e-6)
    assert sol[-1, 1:] == pytest.approx([0.0, 0.0])
