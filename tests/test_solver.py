import numba
import numpy as np
import pytest

from attractors.core.expression_parser import compile_system
from attractors.core.models import AttractorConfig, AttractorParam
from attractors.core.solver import solve_attractor, solve_rk4


@numba.njit(nogil=True)
def _constant_system(state, t, params):
    return np.array([1.0, -2.0, 0.5])


@numba.njit(nogil=True)
def _exponential_x_system(state, t, params):
    x, y, z = state
    return np.array([x, 0.0, 0.0])


@numba.njit(nogil=True)
def _param_order_system(state, t, params):
    a, b, c = params
    return np.array([a, b, c])


@numba.njit(nogil=True)
def _time_system(state, t, params):
    return np.array([t, 0.0, 0.0])


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


def test_solve_rk4_passes_current_time_to_equation():
    y0 = np.array([0.0, 0.0, 0.0])
    params = np.array([], dtype=np.float64)

    sol = solve_rk4(_time_system, y0, 0.0, 2.0, 100, params)

    assert sol[-1, 0] == pytest.approx(2.0, rel=1e-10)
    assert sol[-1, 1:] == pytest.approx([0.0, 0.0])


def test_solve_attractor_supports_custom_time_variable():
    equation, params = compile_system(("t", "0.0", "0.0"))
    config = AttractorConfig(
        name="custom",
        equation=equation,
        params=[],
        initial_conditions=[0.0, 0.0, 0.0],
        time_defaults={"t_min": 0, "t_max": 2, "n": 100},
    )

    sol = solve_attractor(config, {name: 0.0 for name in params})

    assert sol[-1, 0] == pytest.approx(2.0, rel=1e-10)
    assert sol[-1, 1:] == pytest.approx([0.0, 0.0])


def test_solve_attractor_supports_custom_time_variable_with_ic_override():
    equation, params = compile_system(("t + x", "y", "z"))
    config = AttractorConfig(
        name="custom",
        equation=equation,
        params=[],
        initial_conditions=[0.0, 0.0, 0.0],
        time_defaults={"t_min": 0, "t_max": 1, "n": 100},
    )

    sol_a = solve_attractor(config, {name: 0.0 for name in params}, ic=[0.0, 0.0, 0.0])
    sol_b = solve_attractor(config, {name: 0.0 for name in params}, ic=[1.0, 0.0, 0.0])

    assert sol_a[-1, 0] == pytest.approx(np.e - 2.0, rel=1e-6)
    assert sol_b[-1, 0] == pytest.approx(2.0 * np.e - 2.0, rel=1e-6)
    assert sol_b[-1, 0] > sol_a[-1, 0]


def test_solve_attractor_uses_config_defaults():
    config = AttractorConfig(
        name="constant",
        equation=_constant_system,
        params=[],
        initial_conditions=[10.0, 20.0, 30.0],
        time_defaults={"t_min": 0, "t_max": 1, "n": 10},
    )

    sol = solve_attractor(config, {})

    assert sol.shape == (10, 3)
    assert sol[-1] == pytest.approx([11.0, 18.0, 30.5])


def test_solve_attractor_allows_n_tmax_and_ic_overrides():
    config = AttractorConfig(
        name="constant",
        equation=_constant_system,
        params=[],
        initial_conditions=[10.0, 20.0, 30.0],
        time_defaults={"t_min": 0, "t_max": 1, "n": 10},
    )

    sol = solve_attractor(config, {}, n=4, t_max=2.0, ic=[0.0, 0.0, 0.0])

    assert sol.shape == (4, 3)
    assert sol[-1] == pytest.approx([2.0, -4.0, 1.0])


def test_solve_attractor_maps_params_in_config_order():
    config = AttractorConfig(
        name="params",
        equation=_param_order_system,
        params=[
            AttractorParam("b", 0.0, 0.0, 10.0),
            AttractorParam("a", 0.0, 0.0, 0.0, 10.0),
            AttractorParam("c", 0.0, 0.0, 10.0),
        ],
        initial_conditions=[0.0, 0.0, 0.0],
        time_defaults={"t_min": 0, "t_max": 1, "n": 1},
    )

    sol = solve_attractor(config, {"a": 10.0, "b": 20.0, "c": 30.0})

    assert sol[-1] == pytest.approx([20.0, 10.0, 30.0])


def test_solve_attractor_missing_param_raises_key_error():
    config = AttractorConfig(
        name="params",
        equation=_param_order_system,
        params=[
            AttractorParam("a", 0.0, 0.0, 10.0),
        ],
        initial_conditions=[0.0, 0.0, 0.0],
        time_defaults={"t_min": 0, "t_max": 1, "n": 1},
    )

    with pytest.raises(KeyError) as exc_info:
        solve_attractor(config, {})

        assert exc_info.value.args == ("a",)
