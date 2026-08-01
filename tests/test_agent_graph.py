"""Tests for the Reason -> Plan LangGraph graph."""

from app.agent.graph import build_graph
from app.agent.state import create_initial_state


class _FakeLLMClient:
    """Stand-in for GroqClient so graph tests never touch the real SDK."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._responses.pop(0)


def test_graph_populates_intent_and_plan():
    fake_client = _FakeLLMClient(
        responses=[
            "Book a flight",
            '["Search flights", "Pick cheapest", "Confirm booking"]',
        ]
    )

    graph = build_graph(fake_client)

    final_state = graph.invoke(
        create_initial_state("wf-1", "Book me a flight to Paris")
    )

    assert final_state["intent"] == "Book a flight"
    assert final_state["plan"] == [
        "Search flights",
        "Pick cheapest",
        "Confirm booking",
    ]
    assert final_state["status"] == "COMPLETED"
    assert final_state["current_step"] == "DONE"


def test_graph_calls_reason_before_plan_with_correct_prompts():
    fake_client = _FakeLLMClient(
        responses=[
            "Order food",
            '["Pick a restaurant", "Place order"]',
        ]
    )

    graph = build_graph(fake_client)

    graph.invoke(create_initial_state("wf-2", "I'm hungry, order me dinner"))

    assert len(fake_client.calls) == 2
    assert "I'm hungry, order me dinner" in fake_client.calls[0]
    assert "Order food" in fake_client.calls[1]


def test_graph_falls_back_to_single_step_plan_on_malformed_json():
    fake_client = _FakeLLMClient(
        responses=[
            "Do something",
            "not valid json at all",
        ]
    )

    graph = build_graph(fake_client)

    final_state = graph.invoke(
        create_initial_state("wf-3", "Do the thing")
    )

    assert final_state["plan"] == ["Respond to: Do the thing"]
    assert final_state["status"] == "COMPLETED"


def test_graph_preserves_workflow_id():
    fake_client = _FakeLLMClient(
        responses=[
            "intent",
            "[]",
        ]
    )

    graph = build_graph(fake_client)

    final_state = graph.invoke(
        create_initial_state("wf-preserved", "Hello")
    )

    assert final_state["workflow_id"] == "wf-preserved"


def test_graph_preserves_metadata():
    """Metadata from both nodes should be available in the final state."""

    fake_client = _FakeLLMClient(
        responses=[
            "Book a flight",
            '["Search flights"]',
        ]
    )

    graph = build_graph(fake_client)

    final_state = graph.invoke(
        create_initial_state("wf-meta", "Book me a flight")
    )

    assert "reason_raw_response" in final_state["metadata"]
    assert "plan_raw_response" in final_state["metadata"]