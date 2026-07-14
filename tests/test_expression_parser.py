import pytest

from attractors.expression_parser import ParseError, tokenise


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
