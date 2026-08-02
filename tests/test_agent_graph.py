"""Tests for the Reason -> Plan -> Act -> Observe LangGraph graph."""

from app.agent.graph import build_graph
from app.agent.state import create_initial_state
from app.core.exceptions import ToolExecutionError


class _FakeLLMClient:
    """Fake LLM client so graph tests never call real Groq API."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._responses.pop(0)


class _FailingToolExecutor:
    """Fake tool executor used for failure testing."""

    def execute(
        self,
        tool_name: str,
        tool_input: dict,
    ) -> dict:
        raise ToolExecutionError("search backend down")


def test_graph_executes_all_four_nodes_and_produces_final_response():
    fake_client = _FakeLLMClient(
        responses=[
            "Find restaurants",
            '["Search restaurants", "Pick best one"]',
            "Here are some great restaurant options nearby.",
        ]
    )

    graph = build_graph(fake_client)

    final_state = graph.invoke(
        create_initial_state(
            "wf-1",
            "Find me a good restaurant",
        )
    )

    assert final_state["intent"] == "Find restaurants"

    assert final_state["plan"] == [
        "Search restaurants",
        "Pick best one",
    ]

    assert final_state["tool_name"] == "search"

    assert final_state["tool_result"] is not None

    assert final_state["final_response"] == (
        "Here are some great restaurant options nearby."
    )

    assert final_state["status"] == "COMPLETED"
    assert final_state["current_step"] == "DONE"


def test_graph_calls_reason_plan_observe_in_order_with_correct_prompts():
    fake_client = _FakeLLMClient(
        responses=[
            "Order food",
            '["Pick a restaurant", "Place order"]',
            "Your order is on its way!",
        ]
    )

    graph = build_graph(fake_client)

    graph.invoke(
        create_initial_state(
            "wf-2",
            "I'm hungry, order me dinner",
        )
    )

    assert len(fake_client.calls) == 3

    # Reason prompt
    assert "I'm hungry, order me dinner" in fake_client.calls[0]

    # Plan prompt receives intent
    assert "Order food" in fake_client.calls[1]

    # Observe prompt receives context
    assert "Order food" in fake_client.calls[2]


def test_graph_falls_back_to_single_step_plan_on_malformed_json():
    fake_client = _FakeLLMClient(
        responses=[
            "Do something",
            "not valid json at all",
            "Done.",
        ]
    )

    graph = build_graph(fake_client)

    final_state = graph.invoke(
        create_initial_state(
            "wf-3",
            "Do the thing",
        )
    )

    assert final_state["plan"] == [
        "Respond to: Do the thing"
    ]

    assert final_state["status"] == "COMPLETED"


def test_graph_preserves_workflow_id():
    fake_client = _FakeLLMClient(
        responses=[
            "intent",
            "[]",
            "ok",
        ]
    )

    graph = build_graph(fake_client)

    final_state = graph.invoke(
        create_initial_state(
            "wf-preserved",
            "Hello",
        )
    )

    assert final_state["workflow_id"] == "wf-preserved"


def test_graph_marks_failed_when_tool_execution_fails():
    fake_client = _FakeLLMClient(
        responses=[
            "intent",
            "[]",
        ]
    )

    graph = build_graph(
        fake_client,
        tool_executor=_FailingToolExecutor(),
    )

    final_state = graph.invoke(
        create_initial_state(
            "wf-4",
            "Hello",
        )
    )

    assert final_state["status"] == "FAILED"

    assert (
        "error"
        in final_state["metadata"]
    )

    assert final_state["final_response"] is not None

    assert final_state["current_step"] == "DONE"