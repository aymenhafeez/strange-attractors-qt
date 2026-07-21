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



def test_compute_lyapunov_recovers_linear_system_exponents():
    params = np.array([-0.1, -0.2, -0.3], dtype=np.float64)
    initial_conditions = np.array([1.0, 1.0, 1.0], dtype=np.float64)

    lyap, ky_dim, t_hist, lyap_hist = compute_lyapunov(
        _linear_diagonal_system,
        initial_conditions,
        params,
        0.0,
        2.0,
        200,
        gs_interval=10,
    )

    assert lyap == pytest.approx(params, abs=1e-8)
    assert ky_dim == pytest.approx(0.0)
    assert t_hist.shape == (20,)
    assert lyap_hist.shape == (20, 3)


def test_compute_lyapunov_history_tracks_convergence():
    params = np.array([-0.1, -0.2, -0.3], dtype=np.float64)
    initial_conditions = np.array([1.0, 1.0, 1.0], dtype=np.float64)

    lyap, _, t_hist, lyap_hist = compute_lyapunov(
        _linear_diagonal_system,
        initial_conditions,
        params,
        0.0,
        1.0,
        100,
        gs_interval=10,
    )

    assert t_hist == pytest.approx(np.linspace(0.1, 1.0, 10))
    assert lyap_hist[-1] == pytest.approx(lyap)
    assert np.all(np.isfinite(lyap_hist))