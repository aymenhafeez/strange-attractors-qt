# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import ast
import math
from collections.abc import Callable

import numba
import numpy as np


class ParseError(Exception):
    def __init__(self, message: str, pos: int = 0):
        self.pos = pos
        super().__init__(message)


Node = ast.expr

CONSTANTS = {"pi": math.pi, "euler": math.e}
FUNCTIONS = {
    "sin": ("np.sin", 1),
    "cos": ("np.cos", 1),
    "tan": ("np.tan", 1),
    "exp": ("np.exp", 1),
    "log": ("np.log", 1),
    "sqrt": ("np.sqrt", 1),
    "abs": ("np.abs", 1),
    "atan2": ("np.arctan2", 2),
    "pow": ("np.power", 2),
    "min": ("np.minimum", 2),
    "max": ("np.maximum", 2),
    "hypot": ("np.hypot", 2),
}
BIN_OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "**"}
UNARY_OPS = {ast.UAdd: "+", ast.USub: "-"}
STATE_VARS = frozenset({"x", "y", "z", "t"})


def error_position(node: ast.AST) -> int:
    return getattr(node, "col_offset", 0)


def parse_expression(expr: str) -> Node:
    try:
        return ast.parse(expr, mode="eval").body
    except SyntaxError as e:
        pos = max((e.offset or 1) - 1, 0)
        raise ParseError(e.msg, pos) from e


def _emit(node: Node) -> str:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ParseError("Only numbers are supported", error_position(node))
        return repr(float(node.value))

    if isinstance(node, ast.Name):
        if node.id in CONSTANTS:
            return repr(CONSTANTS[node.id])
        if node.id in FUNCTIONS:
            raise ParseError(
                f"Function '{node.id}' needs parentheses", error_position(node)
            )
        return node.id

    if isinstance(node, ast.BinOp):
        op = BIN_OPS.get(type(node.op))
        if op is None:
            raise ParseError("Unsupported operator", error_position(node))
        return f"({_emit(node.left)} {op} {_emit(node.right)})"

    if isinstance(node, ast.UnaryOp):
        op = UNARY_OPS.get(type(node.op))
        if op is None:
            raise ParseError("Unsupported unary operator", error_position(node))

        value = _emit(node.operand)
        return f"(-{value})" if op == "-" else value

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ParseError("Unsupported function call", error_position(node.func))

        function = FUNCTIONS.get(node.func.id)
        if function is None:
            raise ParseError(
                f"Unknown function '{node.func.id}'", error_position(node.func)
            )

        target, arity = function
        if node.keywords or len(node.args) != arity:
            raise ParseError(
                f"Function '{node.func.id}' expects {arity} argument(s)",
                error_position(node.func),
            )

        args = ", ".join(_emit(arg) for arg in node.args)
        return f"{target}({args})"

    raise ParseError(
        f"Unsupported expression: {type(node).__name__}", error_position(node)
    )


def _variables_for_equations(equations: tuple[str, ...]) -> tuple[str, ...]:
    if len(equations) == 2:
        return ("x", "y")
    if len(equations) == 3:
        return ("x", "y", "z")

    raise ParseError("Expected two or three equations")


def detect_parameters(equations: tuple[str, ...]) -> list[str]:
    variables = _variables_for_equations(equations)
    inactive_variables = STATE_VARS - set(variables) - {"t"}
    seen: dict[str, None] = {}

    for equation in equations:
        for node in ast.walk(parse_expression(equation)):
            if not isinstance(node, ast.Name):
                continue

            name = node.id

            if name in inactive_variables:
                raise ParseError(
                    f"Coordinate '{name}' is unavailable in this system",
                    error_position(node),
                )

            if name in {"x_var", "params", "out", "np"}:
                raise ParseError(
                    f"Name '{name}' is reserved",
                    error_position(node),
                )

            if name in STATE_VARS or name in CONSTANTS or name in FUNCTIONS:
                continue

            seen[name] = None

    return list(seen)


def compile_system(equations: tuple[str, ...]) -> tuple[Callable, list[str]]:
    variables = _variables_for_equations(equations)
    params = sorted(detect_parameters(equations))
    emitted = [_emit(parse_expression(equation)) for equation in equations]

    lines = [
        "def _custom(x_var, t, params, out):",
        f"    {', '.join(variables)} = x_var",
    ]

    if params:
        # unpack into a single value if there's only one param
        lines.append(f"    {', '.join(params)}, = params")

    for index, expression in enumerate(emitted):
        lines.append(f"    out[{index}] = {expression}")

    source = "\n".join(lines) + "\n"

    namespace = {"np": np, "__builtins__": {}}
    exec(compile(source, "<custom_attractor>", "exec"), namespace)  # noqa: S102

    func = numba.njit(namespace["_custom"], nogil=True)
    return func, params


def format_equations(equations: tuple[str, ...]) -> str:
    variables = _variables_for_equations(equations)
    return "\n".join(
        f"d{variable}/dt = {equation}"
        for variable, equation in zip(variables, equations, strict=True)
    )
