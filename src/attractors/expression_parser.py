from typing import Union

from dataclasses import dataclass

Token = list[tuple[str, str | float, int]]


class ParseError(Exception):
    """
    Exception raised when parser gets invalid syntax at a given position in the input
    """

    def __init__(self, message: str, pos: int = 0):
        self.pos = pos
        super().__init__(message)


def tokenise(expr: str) -> Token:
    """
    Scan an expression and return a flat list of tokens
    """
    tokens: Token = []

    i = 0
    while i < len(expr):
        ch = expr[i]

        # skip whitespace/tab characters
        if ch in " \t":
            i += 1
            continue

        if ch.isdigit() or ch == ".":
            start = i
            has_dot = ch == "."
            i += 1
            while i < len(expr) and (expr[i].isdigit() or expr[i] == "."):
                if expr[i] == ".":
                    if has_dot:
                        raise ParseError("Invalid number format", i)
                    has_dot = True
                i += 1
            if i < len(expr) and expr[i] in "eE":
                i += 1
                if i < len(expr) and expr[i] in "+-":
                    i += 1
                if i >= len(expr) or not expr[i].isdigit():
                    raise ParseError(
                        f"Invalid scientific notation at position {start}", start
                    )
                while i < len(expr) and expr[i].isdigit():
                    i += 1

            tokens.append(("NUMBER", float(expr[start:i]), start))
            continue

        if ch.isalpha() or ch == "_":
            start = i
            while i < len(expr) and (expr[i].isalnum() or expr[i] == "_"):
                i += 1
            name = expr[start:i]
            tokens.append(("NAME", name, start))
            continue

        if ch in "+-*/":
            # check for ** power operator
            if ch == "*" and i + 1 < len(expr) and expr[i + 1] == "*":
                tokens.append(("OP", "**", i))
                i += 2
                continue
            tokens.append(("OP", ch, i))
            i += 1
            continue

        if ch == "(":
            tokens.append(("LPAREN", ch, i))
            i += 1
            continue
        if ch == ")":
            tokens.append(("RPAREN", ch, i))
            i += 1
            continue
        if ch == ",":
            tokens.append(("COMMA", ch, i))
            i += 1
            continue

        raise ParseError(f"Unexpected character '{ch}' at position {i}", i)

    tokens.append(("END", "", len(expr)))

    return tokens


@dataclass
class Num:
    """Numeric literal"""

    value: float


@dataclass
class Var:
    """Variable reference"""

    name: str


@dataclass
class BinOp:
    """Binary operation, left op right e.g. 2 + 3"""

    op: str
    left: "Node"
    right: "Node"


@dataclass
class UnaryOp:
    """Unary operation, e.g. -x"""

    op: str
    operand: "Node"


@dataclass
class Call:
    """Function call, e.g. sin(x)"""

    func: str
    arg: "Node"


Node = Num | Var | BinOp | UnaryOp | Call

BUILTINS = frozenset({"sin", "cos", "tan", "exp", "log", "sqrt", "abs", "pi", "e"})

STATE_VARS = frozenset({"x", "y", "z", "t"})


class Parser:
    def __init__(self, tokens: Token, expr_str: str):
        self.tokens = tokens
        self.pos = 0
        self.expr_str = expr_str

    def peek(self) -> tuple[str, str | float, int]:
        """
        Look at the current token without consuming it and decide which grammar
        rule to apply
        """
        return self.tokens[self.pos]

    def advance(self) -> tuple[str, str | float, int]:
        """
        Consume the current token, return it and move to the next one
        """
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1

        return tok

    def expect(self, tok_type: str, tok_value: str | None = None):
        """
        Assert the current token if of the expected type and value, consume it
        and return it. Raise ParseError if the assertion fails
        """
        tok_type_got, tok_val, pos = self.peek()
        if tok_type_got != tok_type:
            raise ParseError(
                f"Expected {tok_type} got {tok_type_got} ('{tok_val}') a position {pos}",
                pos,
            )
        if tok_value is not None and tok_val != tok_value:
            raise ParseError(
                f"Expected {tok_value} got '{tok_val}' at position {pos}",
                pos,
            )

        return self.advance()
