"""Tests for the generic BaseRepository and domain repositories."""

import pytest

from app.database.exceptions import RecordNotFoundError
from app.database.repositories import NoteRepository
from app.database.repository import BaseRepository
from app.models.note import Note


def test_create_and_get_by_id(db_session):
    repo = BaseRepository(Note, db_session)
    note = repo.create(title="Groceries", content="Milk, eggs, bread")

    fetched = repo.get_by_id(note.id)
    assert fetched.title == "Groceries"
    assert fetched.content == "Milk, eggs, bread"


def test_get_by_id_raises_when_missing(db_session):
    repo = BaseRepository(Note, db_session)
    with pytest.raises(RecordNotFoundError):
        repo.get_by_id(999)


def test_get_by_id_or_none_returns_none_when_missing(db_session):
    repo = BaseRepository(Note, db_session)
    assert repo.get_by_id_or_none(999) is None


def test_update_modifies_fields(db_session):
    repo = BaseRepository(Note, db_session)
    note = repo.create(title="Old Title", content="Old content")

    updated = repo.update(note.id, title="New Title")
    assert updated.title == "New Title"
    assert updated.content == "Old content"


def test_delete_removes_record(db_session):
    repo = BaseRepository(Note, db_session)
    note = repo.create(title="Temp", content="Delete me")

    repo.delete(note.id)
    with pytest.raises(RecordNotFoundError):
        repo.get_by_id(note.id)


def test_list_all_respects_limit_and_offset(db_session):
    repo = BaseRepository(Note, db_session)
    for i in range(5):
        repo.create(title=f"Note {i}", content="content")

    page_one = repo.list_all(limit=2, offset=0)
    page_two = repo.list_all(limit=2, offset=2)

    assert len(page_one) == 2
    assert len(page_two) == 2
    assert page_one[0].id != page_two[0].id


def test_count_returns_total_records(db_session):
    repo = BaseRepository(Note, db_session)
    assert repo.count() == 0
    repo.create(title="A", content="a")
    repo.create(title="B", content="b")
    assert repo.count() == 2


def test_note_repository_search_matches_title_and_content(db_session):
    repo = NoteRepository(db_session)
    repo.create(title="Meeting notes", content="Discuss roadmap")
    repo.create(title="Shopping list", content="Buy meeting snacks")
    repo.create(title="Unrelated", content="Nothing relevant")

    results = repo.search("meeting")
    titles = {n.title for n in results}
    assert titles == {"Meeting notes", "Shopping list"}