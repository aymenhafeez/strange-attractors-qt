import pytest
import math
import numpy as np

from attractors.expression_parser import (
    BinOp,
    Call,
    _emit,
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
            node = parse_expression("atan(x, y)")
            _emit(node)
        assert exc_info.value.pos != 0

    def test_unknown_single_arg_function_raises_with_position(self):
        with pytest.raises(ParseError) as exc_info:
            node = parse_expression("foobar(x)")
            node = parse_expression("foobar(x)")
            _emit(node)
        assert exc_info.value.pos != 0
