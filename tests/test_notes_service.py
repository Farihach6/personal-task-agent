"""Unit tests for the NotesService business logic layer."""

import pytest

from app.core.exceptions import GuardrailViolation
from app.database.exceptions import RecordNotFoundError
from app.services.notes_service import NotesService


def test_create_note_success(db_session):
    service = NotesService(db_session)
    note = service.create_note("Groceries", "Milk, eggs, bread")

    assert note.id is not None
    assert note.title == "Groceries"
    assert note.content == "Milk, eggs, bread"


def test_create_note_strips_whitespace(db_session):
    service = NotesService(db_session)
    note = service.create_note("  Padded Title  ", "  Padded content  ")

    assert note.title == "Padded Title"
    assert note.content == "Padded content"


def test_create_note_rejects_blank_title(db_session):
    service = NotesService(db_session)
    with pytest.raises(GuardrailViolation):
        service.create_note("   ", "some content")


def test_create_note_rejects_blank_content(db_session):
    service = NotesService(db_session)
    with pytest.raises(GuardrailViolation):
        service.create_note("Title", "   ")


def test_get_note_raises_when_missing(db_session):
    service = NotesService(db_session)
    with pytest.raises(RecordNotFoundError):
        service.get_note(999)


def test_update_note_partial_fields(db_session):
    service = NotesService(db_session)
    note = service.create_note("Old Title", "Old content")

    updated = service.update_note(note.id, title="New Title", content=None)
    assert updated.title == "New Title"
    assert updated.content == "Old content"


def test_update_note_requires_at_least_one_field(db_session):
    service = NotesService(db_session)
    note = service.create_note("Title", "Content")
    with pytest.raises(GuardrailViolation):
        service.update_note(note.id, title=None, content=None)


def test_update_note_rejects_blank_field(db_session):
    service = NotesService(db_session)
    note = service.create_note("Title", "Content")
    with pytest.raises(GuardrailViolation):
        service.update_note(note.id, title="   ", content=None)


def test_delete_note_removes_it(db_session):
    service = NotesService(db_session)
    note = service.create_note("Temp", "Delete me")

    service.delete_note(note.id)
    with pytest.raises(RecordNotFoundError):
        service.get_note(note.id)


def test_list_notes_without_search_returns_all(db_session):
    service = NotesService(db_session)
    service.create_note("A", "content a")
    service.create_note("B", "content b")

    items, total = service.list_notes(limit=10, offset=0)
    assert total == 2
    assert len(items) == 2


def test_list_notes_with_search_filters_correctly(db_session):
    service = NotesService(db_session)
    service.create_note("Meeting notes", "Discuss roadmap")
    service.create_note("Unrelated", "Nothing relevant")

    items, total = service.list_notes(search="meeting", limit=10, offset=0)
    assert total == 1
    assert items[0].title == "Meeting notes"


def test_list_notes_pagination(db_session):
    service = NotesService(db_session)
    for i in range(5):
        service.create_note(f"Note {i}", "content")

    page_one, total = service.list_notes(limit=2, offset=0)
    page_two, _ = service.list_notes(limit=2, offset=2)

    assert total == 5
    assert len(page_one) == 2
    assert len(page_two) == 2
    assert page_one[0].id != page_two[0].id