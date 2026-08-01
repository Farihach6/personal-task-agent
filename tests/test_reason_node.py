"""Unit tests for the reason node."""

from app.agent.nodes.reason_node import build_reason_node
from app.agent.state import create_initial_state


class _FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt: str | None = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response


def test_reason_node_sets_intent_and_advances_step():
    fake_client = _FakeLLMClient("  Book a flight  ")
    node = build_reason_node(fake_client)

    state = create_initial_state("wf-1", "I need to fly to Paris next week")
    result = node(state)

    assert result["intent"] == "Book a flight"
    assert result["current_step"] == "PLAN"
    assert result["status"] == "RUNNING"  # status is only finalized by the plan node


def test_reason_node_includes_user_message_in_prompt():
    fake_client = _FakeLLMClient("some intent")
    node = build_reason_node(fake_client)

    state = create_initial_state("wf-2", "Find me a good pizza place")
    node(state)

    assert "Find me a good pizza place" in fake_client.last_prompt


def test_reason_node_records_raw_response_in_metadata():
    fake_client = _FakeLLMClient("Order food")
    node = build_reason_node(fake_client)

    result = node(create_initial_state("wf-3", "I'm hungry"))

    assert result["metadata"]["reason_raw_response"] == "Order food"