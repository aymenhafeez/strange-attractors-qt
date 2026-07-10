import math

from dataclasses import dataclass
import numba
import numpy as np

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

BUILTINS = frozenset({"sin", "cos", "tan", "exp", "log", "sqrt", "abs", "pi", "E"})

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

    def parse_expr(self) -> Node:
        node = self.parse_term()
        while self.peek()[0] == "OP" and self.peek()[1] in ("+", "-"):
            op = self.advance()[1]
            right = self.parse_term()
            node = BinOp(op, node, right)

        return node

    def parse_term(self) -> Node:
        node = self.parse_unary()
        while self.peek()[0] == "OP" and self.peek()[1] in ("*", "/"):
            op = self.advance()[1]
            right = self.parse_unary()
            node = BinOp(op, node, right)

        return node

    def parse_unary(self) -> Node:
        if self.peek()[0] == "OP" and self.peek()[1] in ("+", "-"):
            op = self.advance()[1]
            operand = self.parse_unary()
            return UnaryOp(op, operand)

        return self.parse_power()

    def parse_power(self) -> Node:
        node = self.parse_atom()
        if self.peek()[0] == "OP" and self.peek()[1] == "**":
            op = self.advance()[1]
            right = self.parse_unary()
            node = BinOp(op, node, right)

        return node

    def parse_atom(self) -> Node:
        tok_type, tok_val, pos = self.peek()

        if tok_type == "NUMBER":
            self.advance()
            return Num(tok_val)

        if tok_type == "LPAREN":
            self.advance()
            node = self.parse_expr()
            self.expect("RPAREN")
            return node

        if tok_type == "NAME":
            name = tok_val
            self.advance()

            if self.peek()[0] == "LPAREN":
                self.advance()
                arg = self.parse_expr()
                self.expect("RPAREN")
                return Call(name, arg)

            if name == "pi":
                return Num(math.pi)
            if name == "e":
                return Num(math.e)

            return Var(name)

        raise ParseError(
            f"Unexpected token '{tok_type}' ('{tok_val}') at position {pos}", pos
        )


def parse_expression(exp_str: str) -> Node:
    """
    Parse a single mathematical expression string into its AST
    """
    tokens = tokenise(exp_str)
    parser = Parser(tokens, exp_str)
    node = parser.parse_expr()

    # shouldn't have anything left after parsing so ParseError it there is
    if parser.peek()[0] != "END":
        pos = parser.peek()[2]
        raise ParseError(
            f"Unexpected token '{parser.peek()[1]}' at position {pos}",
            pos,
        )

    return node


FUNC_MAP = {
    "sin": "np.sin",
    "cos": "np.cos",
    "tan": "np.tan",
    "exp": "np.exp",
    "log": "np.log",
    "sqrt": "np.sqrt",
    "abs": "np.abs",
}


def _emit(node: Node) -> str:
    """
    Translate AST to python code for Numba to JIT compile
    """
    if isinstance(node, Num):
        # use repr for higher precision
        return repr(node.value)

    if isinstance(node, Var):
        return node.name

    if isinstance(node, BinOp):
        left = _emit(node.left)
        right = _emit(node.right)
        return f"({left} {node.op} {right})"

    if isinstance(node, UnaryOp):
        # put - in parentheses to preserve order of operations
        operand = _emit(node.operand)
        if node.op == "-":
            return f"(-{operand})"
        return operand

    if isinstance(node, Call):
        func = FUNC_MAP.get(node.func)
        if func is None:
            raise ParseError(f"Unknown function '{node.func}'", 0)

        arg = _emit(node.arg)
        return f"{func}({arg})"

    raise ParseError(f"Unknown node type: {type(node).__name__}", 0)


def _collect_names(
    node: Node, seen: "dict[str, None] | None" = None
) -> "dict[str, None]":
    """
    Collect all variable names used in the AST, preserving the insertion
    order based on the first seen param. Use a shared dict so callers can
    accumulate across multiple ASTs without having to use a set
    """
    if seen is None:
        seen = {}

    if isinstance(node, Var):
        seen[node.name] = None
    elif isinstance(node, BinOp):
        _collect_names(node.left, seen)
        _collect_names(node.right, seen)
    elif isinstance(node, UnaryOp):
        _collect_names(node.operand, seen)
    elif isinstance(node, Call):
        _collect_names(node.arg, seen)

    return seen


def detect_parameters(equations: tuple[str, str, str]) -> list[str]:
    """
    Scan equation strings and detect what's a state variable and what's a user
    defined parameter. Returns params in first seen order (eq0 -> eq1 -> eq2) so
    the order is always consistent between unpacking the string and creating the
    sliders
    """
    seen: dict[str, None] = {}

    for eq_str in equations:
        node = parse_expression(eq_str)
        _collect_names(node, seen)

    # remove state vars and builtins without ever converting to an unordered set
    params = [name for name in seen if name not in STATE_VARS and name not in BUILTINS]

    return params


_FUNC_TEMPLATE = """\
def _custom(x_var, t, params):
    x, y, z = x_var
    {param_unpack}
    dx_dt = {eq0}
    dy_dt = {eq1}
    dz_dt = {eq2}
    return np.array([dx_dt, dy_dt, dz_dt])
"""


def compile_system(equations: tuple[str, str, str]) -> tuple[callable, list[str]]:
    """
    Parse the ODE's and compile them to Numba JIT'd functions
    """
    asts = [parse_expression(eq) for eq in equations]
    params = detect_parameters(equations)

    emitted = [_emit(ast) for ast in asts]

    if params:
        param_unpack = ", ".join(params) + " = params"
    else:
        param_unpack = "# no parameters"

    source = _FUNC_TEMPLATE.format(
        param_unpack=param_unpack,
        eq0=emitted[0],
        eq1=emitted[1],
        eq2=emitted[2],
    )

    namespace = {"np": np, "__builtins__": {}}
    exec(compile(source, "<custom_atractor>", "exec"), namespace)

    func = namespace["_custom"]

    func = numba.njit(func, nogil=True)

    return func, params


def format_equations(equations: tuple[str, str, str]) -> str:
    """
    Format equations for display in the viewport
    """
    labels = ["dx/dt", "dy/dt", "dz/dt"]
    return "\n".join(f"{label} = {eq}" for label, eq in zip(labels, equations))
