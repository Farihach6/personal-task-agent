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
    assert result["current_step"] == "ACT"


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


def test_plan_node_selects_notes_create_action_for_save_note_request():
    fake_client = _FakeLLMClient('["Create the note"]')
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-6", "Save a note that tomorrow I have a dentist appointment")
    result = node(state)

    assert result["tool_name"] == "notes"
    assert result["tool_input"]["action"] == "create"
    assert "dentist appointment" in result["tool_input"]["content"]


def test_plan_node_selects_notes_list_action_for_show_notes_request():
    fake_client = _FakeLLMClient('["List the notes"]')
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-7", "Show all my notes")
    result = node(state)

    assert result["tool_name"] == "notes"
    assert result["tool_input"] == {"action": "list"}


def test_plan_node_selects_notes_delete_action_and_extracts_note_id():
    fake_client = _FakeLLMClient('["Delete the note"]')
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-8", "Delete note 5")
    result = node(state)

    assert result["tool_name"] == "notes"
    assert result["tool_input"] == {"action": "delete", "note_id": 5}


def test_plan_node_selects_notes_get_action_and_extracts_note_id():
    fake_client = _FakeLLMClient('["Find the note"]')
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-9", "Show note 7")
    result = node(state)

    assert result["tool_name"] == "notes"
    assert result["tool_input"]["action"] == "get"
    assert result["tool_input"]["note_id"] == 7


def test_plan_node_selects_notes_update_action_and_extracts_note_id_and_content():
    fake_client = _FakeLLMClient('["Update the note"]')
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-10", "Update note 3 to say buy bread")
    result = node(state)

    assert result["tool_name"] == "notes"
    assert result["tool_input"]["action"] == "update"
    assert result["tool_input"]["note_id"] == 3
    assert result["tool_input"]["content"] == "buy bread"


def test_plan_node_falls_back_to_search_for_non_note_requests():
    fake_client = _FakeLLMClient('["Search restaurants"]')
    node = build_plan_node(fake_client)

    state = create_initial_state("wf-11", "Find me a good pizza place")
    state["intent"] = "Find pizza"
    result = node(state)

    assert result["tool_name"] == "search"
    assert result["tool_input"] == {"query": "Find pizza"}