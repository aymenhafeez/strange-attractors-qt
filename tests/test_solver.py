import numba
import numpy as np
import pytest

from attractors.solver import solve_rk4


@numba.njit(nogil=True)
def _constant_system(state, t, params):
    return np.array([1.0, -2.0, 0.5])


def test_solve_rk4_returns_expected_shape():
    y0 = np.array([0.0, 0.0, 0.0])
    params = np.array([], dtype=np.float64)

    sol = solve_rk4(_constant_system, y0, 0.0, 1.0, 10, params)

    assert sol.shape == (10, 3)
    assert sol.dtype == np.float64
