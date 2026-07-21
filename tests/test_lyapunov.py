import numba
import numpy as np
import pytest

from attractors.lyapunov import (
    _gram_schmidt,
    _numerical_jacobian,
    compute_lyapunov,
)


@numba.njit(nogil=True)
def _linear_diagonal_system(state, t, params):
    a, b, c = params
    x, y, z = state
    return np.array([a * x, b * y, c * z])


def test_numerical_jacobian_matches_known_linear_system():
    params = np.array([0.1, -0.2, 0.3], dtype=np.float64)

    jac = _numerical_jacobian(
        1.0,
        2.0,
        3.0,
        _linear_diagonal_system,
        params,
    )

    expected = np.array(
        [
            [0.1, 0.0, 0.0],
            [0.0, -0.2, 0.0],
            [0.0, 0.0, 0.3],
        ],
        dtype=np.float64,
    )

    assert jac == pytest.approx(expected)
