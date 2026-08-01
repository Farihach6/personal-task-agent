"""Unit tests for the plan node."""

from app.agent.nodes.plan_node import build_plan_node
from app.agent.state import create_initial_state


class _FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt: str | None = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response


def test_plan_node_parses_valid_json_array():
    fake_client = _FakeLLMClient('["Search flights", "Pick cheapest", "Confirm booking"]')
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-1", "Book me a flight")
    state["intent"] = "Book a flight"
    result = node(state)

    assert result["plan"] == ["Search flights", "Pick cheapest", "Confirm booking"]
    assert result["status"] == "COMPLETED"
    assert result["current_step"] == "DONE"


def test_plan_node_falls_back_on_malformed_json():
    fake_client = _FakeLLMClient("this is not json")
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-2", "Do the thing")
    state["intent"] = "Do something"
    result = node(state)

    assert result["plan"] == ["Respond to: Do the thing"]
    assert result["status"] == "COMPLETED"


def test_plan_node_falls_back_on_empty_json_array():
    fake_client = _FakeLLMClient("[]")
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-3", "Do the thing")
    result = node(state)

    assert result["plan"] == ["Respond to: Do the thing"]


def test_plan_node_falls_back_when_json_is_not_a_list_of_strings():
    fake_client = _FakeLLMClient('[{"step": "not a string"}]')
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-4", "Do the thing")
    result = node(state)

    assert result["plan"] == ["Respond to: Do the thing"]


def test_plan_node_includes_intent_and_message_in_prompt():
    fake_client = _FakeLLMClient("[]")
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-5", "Find a restaurant")
    state["intent"] = "Find dining options"
    node(state)

    assert "Find a restaurant" in fake_client.last_prompt
    assert "Find dining options" in fake_client.last_prompt