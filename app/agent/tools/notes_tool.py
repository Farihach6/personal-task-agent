"""Notes tool.

Lets the agent create, list, read, update, and delete notes by dispatching
to the existing NotesService (Milestone 3) — all note validation and
business rules stay in NotesService; this tool only adapts ToolExecutor's
generic `run(tool_input) -> dict` interface to that service's methods.

Uses an injectable session_factory, defaulting to session_scope, exactly
like WorkflowService — because this runs inside the agent graph (outside
FastAPI's per-request session lifecycle), and injection lets tests bind it
to the isolated in-memory database instead of the real engine.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import GuardrailViolation
from app.database.exceptions import RecordNotFoundError
from app.database.session import session_scope
from app.models.note import Note
from app.services.notes_service import NotesService


def _serialize_note(note: Note) -> dict[str, Any]:
    return {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


class NotesTool:
    """Agent-facing adapter over NotesService."""

    name = "notes"

    def __init__(
        self, session_factory: Callable[[], AbstractContextManager[Session]] = session_scope
    ) -> None:
        self._session_factory = session_factory

    def run(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Dispatch to the requested notes action.

        Raises:
            GuardrailViolation: for an unknown/missing action, or one propagated
                from NotesService's own validation (blank title/content, etc.).
        """
        tool_input = tool_input or {}
        action = tool_input.get("action")

        if action == "create":
            return self._create_note(tool_input)
        if action == "list":
            return self._list_notes(tool_input)
        if action == "get":
            return self._get_note(tool_input)
        if action == "update":
            return self._update_note(tool_input)
        if action == "delete":
            return self._delete_note(tool_input)

        raise GuardrailViolation(f"Unknown notes action: {action!r}")

    def _create_note(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        content = (tool_input.get("content") or "").strip()
        title = (tool_input.get("title") or "").strip() or content[:60]

        with self._session_factory() as db:
            note = NotesService(db).create_note(title=title, content=content)
            return {"observation": "note_created", "note": _serialize_note(note)}

    def _list_notes(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        limit = tool_input.get("limit", 20)

        with self._session_factory() as db:
            items, total = NotesService(db).list_notes(limit=limit, offset=0)
            return {
                "observation": "notes_listed",
                "total": total,
                "notes": [_serialize_note(n) for n in items],
            }

    def _get_note(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        note_id = tool_input.get("note_id")
        if note_id is None:
            raise GuardrailViolation("A note_id is required to get a note.")

        with self._session_factory() as db:
            try:
                note = NotesService(db).get_note(int(note_id))
            except RecordNotFoundError:
                return {"observation": "note_not_found", "note_id": note_id}
            return {"observation": "note_found", "note": _serialize_note(note)}

    def _update_note(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        note_id = tool_input.get("note_id")
        if note_id is None:
            raise GuardrailViolation("A note_id is required to update a note.")

        with self._session_factory() as db:
            try:
                note = NotesService(db).update_note(
                    int(note_id),
                    title=tool_input.get("title"),
                    content=tool_input.get("content"),
                )
            except RecordNotFoundError:
                return {"observation": "note_not_found", "note_id": note_id}
            return {"observation": "note_updated", "note": _serialize_note(note)}

    def _delete_note(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        note_id = tool_input.get("note_id")
        if note_id is None:
            raise GuardrailViolation("A note_id is required to delete a note.")

        with self._session_factory() as db:
            try:
                NotesService(db).delete_note(int(note_id))
            except RecordNotFoundError:
                return {"observation": "note_not_found", "note_id": note_id}
            return {"observation": "note_deleted", "note_id": note_id}