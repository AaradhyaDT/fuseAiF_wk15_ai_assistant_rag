import json

import pytest

from app.tools import ToolContext, execute_tool


class _Retriever:
    def context_block(self, query, k=None):
        if "quantum" in query:
            return "[doc:alpha.md] quantum entanglement...", []
        return "", []


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2+2*3", "8"),
        ("(2+3)*4", "20"),
        ("2**10", "1024"),
        ("10/4", "2.5"),
    ],
)
def test_calculator_valid(expression, expected):
    result = execute_tool("calculator", {"expression": expression}, ToolContext())
    assert float(result) == float(expected)


def test_calculator_division_by_zero_is_handled():
    result = execute_tool("calculator", {"expression": "1/0"}, ToolContext())
    assert "error" in result


def test_calculator_rejects_non_numeric_constants():
    result = execute_tool("calculator", {"expression": "__import__('os')"}, ToolContext())
    assert "error" in result


def test_calculator_rejects_attribute_access():
    result = execute_tool("calculator", {"expression": "(1).real"}, ToolContext())
    assert "error" in result


def test_current_datetime_iso_shape():
    result = execute_tool("current_datetime", {}, ToolContext())
    assert result.endswith("Z") and "T" in result


def test_search_knowledge_base_hits():
    result = execute_tool(
        "search_knowledge_base", {"query": "quantum"}, ToolContext(retriever=_Retriever())
    )
    assert "alpha.md" in result


def test_search_knowledge_base_misses():
    result = execute_tool(
        "search_knowledge_base", {"query": "nothing"}, ToolContext(retriever=_Retriever())
    )
    assert json.loads(result)["result"] == "no matching documents"


def test_unknown_tool_raises():
    with pytest.raises(KeyError):
        execute_tool("nope", {}, ToolContext())
