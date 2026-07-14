import pytest
import math
import numpy as np

from attractors.expression_parser import (
    BinOp,
    Call,
    _emit,
    compile_system,
    detect_parameters,
    Num,
    ParseError,
    parse_expression,
    tokenise,
    UnaryOp,
    Var,
)


class TestTokenise:
    def test_integer(self):
        tokens = tokenise("42")
        assert tokens[0] == ("NUMBER", 42.0, 0)

    def test_float(self):
        tokens = tokenise("3.14")
        assert tokens[0] == ("NUMBER", 3.14, 0)

    def test_scientific_lower(self):
        tokens = tokenise("1.5e-3")
        assert tokens[0][0] == "NUMBER"
        assert tokens[0][1] == pytest.approx(1.5e-3)

    def test_scientific_upper(self):
        tokens = tokenise("1E+10")
        assert tokens[0][1] == pytest.approx(1e10)

    def test_name(self):
        tokens = tokenise("x")
        assert tokens[0] == ("NAME", "x", 0)

    def test_operators(self):
        ops = tokenise("+-*/")
        assert [t[1] for t in ops[:-1]] == ["+", "-", "*", "/"]

    def test_power_operator(self):
        tokens = tokenise("x**2")
        assert tokens[1] == ("OP", "**", 1)

    def test_comma(self):
        tokens = tokenise("a,b")
        assert tokens[1][0] == "COMMA"

    def test_end_sentinel(self):
        tokens = tokenise("x")
        assert tokens[-1][0] == "END"

    def test_invalid_character(self):
        with pytest.raises(ParseError):
            tokenise("x @ y")

    def test_double_dot_raises(self):
        with pytest.raises(ParseError):
            tokenise("1.2.3")

    def test_invalid_scientific_notation(self):
        with pytest.raises(ParseError):
            tokenise("1eX")


class TestParseExpression:
    def test_numbe(self):
        assert parse_expression("3.14") == Num(3.14)

    def test_variable(self):
        assert parse_expression("x") == Var("x")

    def test_addition(self):
        node = parse_expression("x + y")
        assert isinstance(node, BinOp)
        assert node.op == "+"

    def test_precedence_mul_over_add(self):
        node = parse_expression("2 + 3 * 4")
        assert isinstance(node, BinOp) and node.op == "+"
        assert isinstance(node.right, BinOp) and node.right.op == "*"

    def test_precedence_paren_override(self):
        node = parse_expression("(2 + 3) * 4")
        assert isinstance(node, BinOp) and node.op == "*"
        assert isinstance(node.left, BinOp) and node.left.op == "+"

    def test_power_right_associative(self):
        node = parse_expression("2**3**2")
        assert isinstance(node, BinOp) and node.op == "**"
        assert isinstance(node.right, BinOp) and node.right.op == "**"

    def test_unary_minus(self):
        node = parse_expression("-x")
        assert isinstance(node, UnaryOp) and node.op == "-"

    def test_unary_double_minus(self):
        node = parse_expression("--x")
        assert isinstance(node, UnaryOp)
        assert isinstance(node.operand, UnaryOp)

    def test_constant_pi(self):
        assert parse_expression("pi") == Num(math.pi)

    def test_contant_euler(self):
        assert parse_expression("euler") == Num(math.e)

    def test_leftover_tokens_raises(self):
        with pytest.raises(ParseError):
            parse_expression("x y")


class TestSingleArgFunctions:
    @pytest.mark.parametrize("fn", ["sin", "cos", "tan", "exp", "log", "sqrt", "abs"])
    def test_parses(self, fn):
        node = parse_expression(f"{fn}(x)")
        assert isinstance(node, Call)
        assert node.func == fn
        assert len(node.args) == 1

    @pytest.mark.parametrize(
        "fn,np_fn",
        [
            ("sin", "np.sin"),
            ("cos", "np.cos"),
            ("tan", "np.tan"),
            ("exp", "np.exp"),
            ("log", "np.log"),
            ("sqrt", "np.sqrt"),
            ("abs", "np.abs"),
        ],
    )
    def test_emits(self, fn, np_fn):
        node = parse_expression(f"{fn}(x)")
        assert _emit(node) == f"{np_fn}(x)"


class TestMultiArgFunctions:
    @pytest.mark.parametrize(
        "expr,expected_np",
        [
            ("atan2(y, x)", "np.arctan2(y, x)"),
            ("pow(x, 2.0)", f"np.power(x, {repr(2.0)})"),
            ("min(a, b)", "np.minimum(a, b)"),
            ("max(a, b)", "np.maximum(a, b)"),
            ("hypot(x, y)", "np.hypot(x, y)"),
        ],
    )
    def test_emits(self, expr, expected_np):
        node = parse_expression(expr)
        assert isinstance(node, Call)
        assert len(node.args) == 2
        assert _emit(node) == expected_np

    def test_unknown_function_raises_with_position(self):
        with pytest.raises(ParseError) as exc_info:
            node = parse_expression("x + atan(x, y)")
            _emit(node)
        assert exc_info.value.pos != 0

    def test_unknown_single_arg_function_raises_with_position(self):
        with pytest.raises(ParseError) as exc_info:
            node = parse_expression("x + foobar(x)")
            _emit(node)
        assert exc_info.value.pos != 0


class TestDetectParameters:
    def test_excludes_state_vars(self):
        params = detect_parameters(("x + y", "z - t", "x * z"))
        assert set(params) == set()

    def test_excludes_builtins(self):
        params = detect_parameters(("sin(x)", "cos(y)", "exp(z)"))
        assert set(params) == set()

    def test_detects_free_params(self):
        params = detect_parameters(("a * (y - x)", "x * (b - z) - y", "x * y - c * z"))
        assert set(params) == {"a", "b", "c"}

    def test_first_seen_order(self):
        params = detect_parameters(("a * x", "b * y", "c * z"))
        assert params == ["a", "b", "c"]

    def test_empty_params(self):
        params = detect_parameters(("y", "-x", "0.0 * z"))
        assert params == []

    def test_multiarg_function_args_not_detected_as_params(self):
        params = detect_parameters(("atan2(y, x)", "z", "0.0 * z"))
        assert set(params) == set()


class TestCompileSystem:
    def test_returns_callable_and_param_list(self):
        func, params = compile_system(
            ("a * (y - x)", "x * (b - z) - y", "x * y - c * z")
        )
        assert callable(func)
        # alphabetical
        assert params == ["a", "b", "c"]

    def test_params_are_alphabetically_sorted(self):
        _, params = compile_system(("c * x", "a * y", "b * z"))
        assert params == ["a", "b", "c"]

    def test_zero_param_system_callable(self):
        func, params = compile_system(("y", "-x", "-z"))
        assert params == []
        result = func(np.array([1.0, 0.0, 0.5]), 0.0, np.array([], dtype=np.float64))
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(-1.0)
        assert result[2] == pytest.approx(-0.5)

    def test_single_param_system_callable(self):
        func, params = compile_system(("a * x", "y", "z"))
        assert params == ["a"]
        result = func(np.array([2.0, 1.0, 1.0]), 0.0, np.array([3.0]))
        assert result[0] == pytest.approx(6.0)

    def test_lorenz_spot_check(self):
        # Lorenz: dx = s(y-x), dy = x(r-z)-y, dz = xy - b*z
        # at (1,1,1) with s=10, r=28, b=8/3:
        # dx = 10*(1-1) = 0, dy = 1*(28-1)-1 = 26, dz = 1 - 8/3 ≈ -1.6667
        func, _ = compile_system(
            (
                "s * (y - x)",
                "x * (r - z) - y",
                "x * y - b * z",
            )
        )
        state = np.array([1.0, 1.0, 1.0])
        # alphabetical
        params = np.array([8 / 3, 28.0, 10.0])
        result = func(state, 0.0, params)
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(26.0)
        assert result[2] == pytest.approx(1.0 - 8 / 3)

    def test_parse_error_surfaces(self):
        with pytest.raises(ParseError):
            # unclosed paren
            compile_system(("a * (y - x", "y", "z"))
