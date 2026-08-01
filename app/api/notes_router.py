"""Notes API router."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.note import NoteCreate, NoteListResponse, NoteResponse, NoteUpdate
from app.services.notes_service import NotesService

router = APIRouter(prefix="/notes", tags=["notes"])


def get_notes_service(db: Session = Depends(get_db)) -> NotesService:
    """FastAPI dependency that builds a NotesService bound to the request's DB session."""
    return NotesService(db)


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate, service: NotesService = Depends(get_notes_service)
) -> NoteResponse:
    """Create a new note."""
    note = service.create_note(title=payload.title, content=payload.content)
    return NoteResponse.model_validate(note)


@router.get("", response_model=NoteListResponse)
def list_notes(
    search: str | None = Query(default=None, description="Search notes by title or content"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: NotesService = Depends(get_notes_service),
) -> NoteListResponse:
    """List notes with optional search and pagination."""
    items, total = service.list_notes(search=search, limit=limit, offset=offset)
    return NoteListResponse(
        items=[NoteResponse.model_validate(n) for n in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{note_id}", response_model=NoteResponse)
def get_note(note_id: int, service: NotesService = Depends(get_notes_service)) -> NoteResponse:
    """Fetch a single note by id."""
    note = service.get_note(note_id)
    return NoteResponse.model_validate(note)


@router.put("/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: int, payload: NoteUpdate, service: NotesService = Depends(get_notes_service)
) -> NoteResponse:
    """Update a note's title and/or content."""
    note = service.update_note(note_id, title=payload.title, content=payload.content)
    return NoteResponse.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, service: NotesService = Depends(get_notes_service)) -> None:
    """Delete a note by id."""
    service.delete_note(note_id)