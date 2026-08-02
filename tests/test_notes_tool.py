"""Tests for NotesTool, bound to the isolated in-memory test database via
the existing workflow_session_factory fixture (same pattern used for
WorkflowService's tests)."""

import pytest

from app.agent.tools.notes_tool import NotesTool
from app.core.exceptions import GuardrailViolation
from app.database.repositories import NoteRepository


def test_notes_tool_create_action_persists_note(workflow_session_factory, db_session):
    tool = NotesTool(session_factory=workflow_session_factory)

    result = tool.run({"action": "create", "title": "Dentist", "content": "Dentist appointment tomorrow"})

    assert result["observation"] == "note_created"
    note_id = result["note"]["id"]
    note = NoteRepository(db_session).get_by_id(note_id)
    assert note.title == "Dentist"
    assert note.content == "Dentist appointment tomorrow"


def test_notes_tool_create_action_derives_title_when_missing(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)

    result = tool.run({"action": "create", "content": "Buy milk and eggs"})

    assert result["note"]["title"] == "Buy milk and eggs"


def test_notes_tool_create_action_raises_on_blank_content(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)

    with pytest.raises(GuardrailViolation):
        tool.run({"action": "create", "content": "   "})


def test_notes_tool_list_action_returns_all_notes(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)
    tool.run({"action": "create", "title": "A", "content": "a"})
    tool.run({"action": "create", "title": "B", "content": "b"})

    result = tool.run({"action": "list"})

    assert result["observation"] == "notes_listed"
    assert result["total"] == 2
    assert len(result["notes"]) == 2


def test_notes_tool_list_action_returns_empty_when_no_notes(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)

    result = tool.run({"action": "list"})

    assert result["observation"] == "notes_listed"
    assert result["total"] == 0
    assert result["notes"] == []


def test_notes_tool_get_action_returns_existing_note(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)
    created = tool.run({"action": "create", "title": "T", "content": "C"})
    note_id = created["note"]["id"]

    result = tool.run({"action": "get", "note_id": note_id})

    assert result["observation"] == "note_found"
    assert result["note"]["id"] == note_id


def test_notes_tool_get_action_handles_missing_note(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)

    result = tool.run({"action": "get", "note_id": 9999})

    assert result["observation"] == "note_not_found"
    assert result["note_id"] == 9999


def test_notes_tool_get_action_requires_note_id(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)

    with pytest.raises(GuardrailViolation):
        tool.run({"action": "get"})


def test_notes_tool_update_action_modifies_note(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)
    created = tool.run({"action": "create", "title": "Old", "content": "Old content"})
    note_id = created["note"]["id"]

    result = tool.run({"action": "update", "note_id": note_id, "title": "New"})

    assert result["observation"] == "note_updated"
    assert result["note"]["title"] == "New"
    assert result["note"]["content"] == "Old content"


def test_notes_tool_update_action_handles_missing_note(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)

    result = tool.run({"action": "update", "note_id": 9999, "title": "X"})

    assert result["observation"] == "note_not_found"


def test_notes_tool_delete_action_removes_note(workflow_session_factory, db_session):
    tool = NotesTool(session_factory=workflow_session_factory)
    created = tool.run({"action": "create", "title": "Temp", "content": "Delete me"})
    note_id = created["note"]["id"]

    result = tool.run({"action": "delete", "note_id": note_id})

    assert result["observation"] == "note_deleted"
    assert NoteRepository(db_session).get_by_id_or_none(note_id) is None


def test_notes_tool_delete_action_handles_missing_note(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)

    result = tool.run({"action": "delete", "note_id": 9999})

    assert result["observation"] == "note_not_found"


def test_notes_tool_rejects_unknown_action(workflow_session_factory):
    tool = NotesTool(session_factory=workflow_session_factory)

    with pytest.raises(GuardrailViolation):
        tool.run({"action": "fly_to_moon"})


def test_notes_tool_has_expected_name():
    assert NotesTool().name == "notes"