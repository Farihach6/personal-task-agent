"""Tests for the mock SearchTool."""

import pytest

from app.agent.tools.search_tool import SearchTool
from app.core.exceptions import GuardrailViolation


def test_search_tool_returns_results_for_valid_query():
    tool = SearchTool()
    result = tool.run({"query": "best pizza in rome"})

    assert result["query"] == "best pizza in rome"
    assert len(result["results"]) == 3
    for item in result["results"]:
        assert "title" in item
        assert "snippet" in item
        assert "url" in item


def test_search_tool_rejects_blank_query():
    tool = SearchTool()
    with pytest.raises(GuardrailViolation):
        tool.run({"query": "   "})


def test_search_tool_rejects_missing_query_key():
    tool = SearchTool()
    with pytest.raises(GuardrailViolation):
        tool.run({})


def test_search_tool_rejects_none_input():
    tool = SearchTool()
    with pytest.raises(GuardrailViolation):
        tool.run(None)


def test_search_tool_has_expected_name():
    assert SearchTool().name == "search"