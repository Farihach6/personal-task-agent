"""Unit tests for the act node."""

from app.agent.nodes.act_node import build_act_node
from app.agent.state import create_initial_state
from app.agent.tools.tool_executor import ToolExecutor
from app.core.exceptions import ToolExecutionError


class _FakeToolExecutor:
    def __init__(
        self, result=None, error: Exception | None = None, requires_approval_value: bool = False
    ) -> None:
        self.result = result
        self.error = error
        self.requires_approval_value = requires_approval_value
        self.calls: list[tuple[str, dict]] = []

    def execute(self, tool_name: str, tool_input: dict) -> dict:
        self.calls.append((tool_name, tool_input))
        if self.error is not None:
            raise self.error
        return self.result

    def requires_approval(self, tool_name: str) -> bool:
        return self.requires_approval_value


def test_act_node_executes_search_and_stores_result():
    fake_executor = _FakeToolExecutor(result={"query": "pizza", "results": []})
    node = build_act_node(fake_executor)

    state = create_initial_state("wf-1", "Find pizza")
    state["intent"] = "pizza"
    result = node(state)

    assert result["tool_name"] == "search"
    assert result["tool_input"] == {"query": "pizza"}
    assert result["tool_result"] == {"query": "pizza", "results": []}
    assert result["current_step"] == "OBSERVE"
    assert result["status"] == "RUNNING"


def test_act_node_falls_back_to_user_message_when_intent_is_blank():
    fake_executor = _FakeToolExecutor(result={"query": "hi", "results": []})
    node = build_act_node(fake_executor)

    state = create_initial_state("wf-2", "hi")
    node(state)

    assert fake_executor.calls[0] == ("search", {"query": "hi"})


def test_act_node_marks_failed_on_tool_error():
    fake_executor = _FakeToolExecutor(error=ToolExecutionError("search backend down"))
    node = build_act_node(fake_executor)

    state = create_initial_state("wf-3", "Find pizza")
    state["intent"] = "pizza"
    result = node(state)

    assert result["status"] == "FAILED"
    assert result["tool_result"] is None
    assert result["metadata"]["error"] == "search backend down"
    # Still advances toward Observe so the graph can finalize cleanly.
    assert result["current_step"] == "OBSERVE"


def test_act_node_records_tool_name_and_input_even_on_failure():
    fake_executor = _FakeToolExecutor(error=RuntimeError("boom"))
    node = build_act_node(fake_executor)

    state = create_initial_state("wf-4", "Find sushi")
    state["intent"] = "sushi"
    result = node(state)

    assert result["tool_name"] == "search"
    assert result["tool_input"] == {"query": "sushi"}


def test_act_node_pauses_for_approval_when_tool_requires_it():
    fake_executor = _FakeToolExecutor(
        result={"observation": "email_sent"}, requires_approval_value=True
    )
    node = build_act_node(fake_executor)

    state = create_initial_state("wf-5", "Send an email to john@example.com saying hi")
    state["tool_name"] = "email"
    state["tool_input"] = {"to": "john@example.com", "subject": "Hi", "body": "hi"}
    result = node(state)

    assert result["status"] == "WAITING_APPROVAL"
    assert result["current_step"] == "AWAITING_APPROVAL"
    assert result["metadata"]["approval_required"] is True


def test_act_node_does_not_execute_tool_when_paused_for_approval():
    fake_executor = _FakeToolExecutor(
        result={"observation": "email_sent"}, requires_approval_value=True
    )
    node = build_act_node(fake_executor)

    state = create_initial_state("wf-6", "Send an email to john@example.com saying hi")
    state["tool_name"] = "email"
    state["tool_input"] = {"to": "john@example.com", "body": "hi"}
    result = node(state)

    assert fake_executor.calls == []
    assert result["tool_result"] is None


def test_act_node_marks_failed_when_tool_name_is_unrecognized():
    """Regression: if the planner ever selects a tool_name the executor
    doesn't recognize, ToolExecutor.requires_approval() raises before
    execution even starts — Act must still catch this and fail gracefully
    rather than crash the graph."""
    real_executor = ToolExecutor()  # default registry: search, notes, email — no "carrier_pigeon"
    node = build_act_node(real_executor)

    state = create_initial_state("wf-7", "Do something unusual")
    state["tool_name"] = "carrier_pigeon"
    state["tool_input"] = {}
    result = node(state)

    assert result["status"] == "FAILED"
    assert result["current_step"] == "OBSERVE"
    assert result["tool_result"] is None
    assert "error" in result["metadata"]