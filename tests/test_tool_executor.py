"""Tests for ToolExecutor."""

import pytest

from app.agent.tools.notes_tool import NotesTool
from app.agent.tools.search_tool import SearchTool
from app.agent.tools.tool_executor import ToolExecutor
from app.core.exceptions import GuardrailViolation, ToolExecutionError


def test_tool_executor_dispatches_to_search_tool_by_default():
    executor = ToolExecutor()
    result = executor.execute("search", {"query": "weather in Paris"})

    assert result["query"] == "weather in Paris"


def test_tool_executor_raises_tool_execution_error_for_unknown_tool():
    executor = ToolExecutor()
    with pytest.raises(ToolExecutionError):
        executor.execute("nonexistent_tool", {})


def test_tool_executor_wraps_unexpected_exceptions_as_tool_execution_error():
    class _BoomTool:
        name = "boom"

        def run(self, tool_input):
            raise RuntimeError("kaboom")

    executor = ToolExecutor(tools=[_BoomTool()])
    with pytest.raises(ToolExecutionError):
        executor.execute("boom", {})


def test_tool_executor_propagates_guardrail_violations_unwrapped():
    executor = ToolExecutor()
    with pytest.raises(GuardrailViolation):
        executor.execute("search", {"query": ""})


def test_tool_executor_is_extendable_with_custom_tools():
    class _EchoTool:
        name = "echo"

        def run(self, tool_input):
            return {"echoed": tool_input}

    executor = ToolExecutor(tools=[SearchTool(), _EchoTool()])

    assert executor.execute("echo", {"x": 1}) == {"echoed": {"x": 1}}
    assert executor.execute("search", {"query": "still works"})["query"] == "still works"


def test_tool_executor_dispatches_to_notes_tool(workflow_session_factory):
    executor = ToolExecutor(tools=[SearchTool(), NotesTool(session_factory=workflow_session_factory)])

    result = executor.execute("notes", {"action": "list"})

    assert result["observation"] == "notes_listed"
    assert result["total"] == 0


def test_tool_executor_default_registry_includes_search_and_notes():
    # Regression check: adding NotesTool must not remove or shadow SearchTool.
    executor = ToolExecutor()

    assert "search" in executor._tools
    assert "notes" in executor._tools
    assert isinstance(executor._tools["search"], SearchTool)
    assert isinstance(executor._tools["notes"], NotesTool)