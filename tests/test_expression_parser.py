import numpy as np
import pytest

from attractors.core.expression_parser import (
    compile_system,
)


def evaluate(equations, state=None, params=None):
    func, param_names = compile_system(equations)
    state = np.array(state or [0.0, 0.0, 0.0])
    params = np.array(params or [])

    return func(state, 0.0, params), param_names


def test_compile_op_order():
    result, params = evaluate(("2 + 3 * 4", "(2 + 3) * 4", "2**3**2"))

    assert params == []
    assert result == pytest.approx([14.0, 20.0, 512.0])


def test_compile_supports_unary_and_constants():
    result, params = evaluate(("-x", "pi", "euler"), state=[2.0, 0.0, 0.0])

    assert params == []
    assert result == pytest.approx([-2.0, np.pi, np.e])


def test_compile_supports_functions():
    result, params = evaluate(
        ("sin(x)", "atan2(y, x)", "sqrt(z)"),
        state=[1.0, 2.0, 4.0],
    )

    assert params == []
    assert result == pytest.approx([np.sin(1.0), np.arctan2(2.0, 1.0), 2.0])


def test_param_evaluation():
    func, params = compile_system(
        (
            "s * (y - x)",
            "x * (r - z) - y",
            "x * y - b * z",
        )
    )

    result = func(
        np.array([1.0, 1.0, 1.0]),
        0.0,
        np.array([8 / 3, 28.0, 10.0]),
    )

    assert params == ["b", "r", "s"]
    assert result == pytest.approx([0.0, 26.0, 1.0 - 8 / 3])
