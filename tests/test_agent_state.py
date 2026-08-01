"""Tests for the AgentState structure and its initial-state factory."""

from app.agent.state import create_initial_state


def test_create_initial_state_sets_all_fields():
    state = create_initial_state("wf-123", "Book me a flight to Paris")

    assert state["workflow_id"] == "wf-123"
    assert state["user_message"] == "Book me a flight to Paris"
    assert state["intent"] == ""
    assert state["plan"] == []
    assert state["current_step"] == "REASON"
    assert state["status"] == "RUNNING"
    assert state["metadata"] == {}


def test_create_initial_state_is_independent_per_call():
    state_one = create_initial_state("wf-1", "First")
    state_two = create_initial_state("wf-2", "Second")

    state_one["plan"].append("mutated")
    state_one["metadata"]["key"] = "value"

    assert state_two["plan"] == []
    assert state_two["metadata"] == {}
    assert state_one["workflow_id"] != state_two["workflow_id"]


def test_create_initial_state_allows_none_workflow_id():
    state = create_initial_state(None, "Hello")
    assert state["workflow_id"] is None