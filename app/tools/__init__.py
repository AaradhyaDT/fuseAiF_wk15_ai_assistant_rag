import ast
import json
import time
from dataclasses import dataclass
from typing import Any

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate an arithmetic expression (+, -, *, /, //, %, **).",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "current_datetime",
            "description": "Return the current UTC date and time in ISO format.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Semantic search over the ingested document corpus.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
)

_MAX_ABS_EXPONENT = 10_000


def calculate(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return "error: invalid expression"
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return "error: disallowed syntax"
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            return "error: only numeric constants allowed"
        if (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Pow)
            and isinstance(node.right, ast.Constant)
            and abs(float(node.right.value)) > _MAX_ABS_EXPONENT
        ):
            return "error: exponent too large"
    try:
        value = eval(compile(tree, "<calculator>", "eval"), {"__builtins__": {}}, {})
    except ZeroDivisionError:
        return "error: division by zero"
    except (OverflowError, ArithmeticError) as exc:
        return f"error: {exc.__class__.__name__}"
    return repr(round(value, 6))


@dataclass
class ToolContext:
    retriever: Any = None


def execute_tool(name: str, arguments: dict, ctx: ToolContext) -> str:
    if name == "calculator":
        return calculate(str(arguments.get("expression", "")))
    if name == "current_datetime":
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if name == "search_knowledge_base":
        query = str(arguments.get("query", ""))
        if ctx.retriever is None:
            return json.dumps({"error": "retriever unavailable"})
        block, _sources = ctx.retriever.context_block(query, k=3)
        return block if block else json.dumps({"result": "no matching documents"})
    raise KeyError(f"unknown tool: {name}")
