"""Tool registry. The calculator evaluates arithmetic through an AST whitelist, never eval()."""
from __future__ import annotations

import ast
import operator

MAX_EXPR_LEN = 200
MAX_EXPONENT = 1000

_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise ValueError("exponent too large")
        return _BIN[type(node.op)](left, right)
    raise ValueError("unsupported syntax: only numbers and + - * / // % ** ( ) are allowed")


def calculator(expression: str) -> str:
    """Return the result as text. Errors are returned as text so the model can retry."""
    if not isinstance(expression, str) or not expression.strip():
        return "error: expression must be a non-empty string"
    if len(expression) > MAX_EXPR_LEN:
        return f"error: expression longer than {MAX_EXPR_LEN} characters"
    try:
        value = _eval(ast.parse(expression.strip(), mode="eval"))
    except ZeroDivisionError:
        return "error: division by zero"
    except (ValueError, SyntaxError, OverflowError) as exc:
        return f"error: {exc}"
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        value = int(value)
    return str(value)


TOOLS = {"calculator": calculator}

SCHEMAS = [{
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Evaluate an arithmetic expression. Supports + - * / // % ** and parentheses.",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "e.g. 17*23+4"}},
            "required": ["expression"],
        },
    },
}]


def run_tool(name: str, arguments) -> str:
    fn = TOOLS.get(name)
    if fn is None:
        return f"error: unknown tool '{name}'. Available: {', '.join(TOOLS)}"
    if not isinstance(arguments, dict):
        return "error: arguments must be an object"
    try:
        return fn(**arguments)
    except TypeError as exc:
        return f"error: bad arguments: {exc}"
