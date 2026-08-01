"""Business logic for the Notes feature.

Route handlers stay thin and delegate all validation/orchestration here,
which in turn is the only layer allowed to call the repository directly.
"""

from sqlalchemy.orm import Session

from app.core.exceptions import GuardrailViolation
from app.database.repositories import NoteRepository
from app.models.note import Note


class NotesService:
    """Encapsulates business rules for creating, reading, updating, and
    deleting notes."""

    def __init__(self, db: Session) -> None:
        self.repo = NoteRepository(db)

    def create_note(self, title: str, content: str) -> Note:
        """Create a note after normalizing and validating its fields."""
        title = title.strip()
        content = content.strip()
        if not title or not content:
            raise GuardrailViolation("Note title and content cannot be empty.")
        return self.repo.create(title=title, content=content)

    def get_note(self, note_id: int) -> Note:
        """Fetch a single note by id (raises RecordNotFoundError if missing)."""
        return self.repo.get_by_id(note_id)

    def list_notes(
        self, search: str | None = None, limit: int = 20, offset: int = 0
    ) -> tuple[list[Note], int]:
        """Return a page of notes plus the total matching count.

        Delegates to a search-filtered query when `search` is provided,
        otherwise returns all notes ordered by most recently updated.
        """
        if search and search.strip():
            search = search.strip()
            items = self.repo.search(search, limit=limit, offset=offset)
            total = self.repo.count_search(search)
        else:
            items = self.repo.get_all_ordered(limit=limit, offset=offset)
            total = self.repo.count()
        return items, total

    def update_note(self, note_id: int, title: str | None, content: str | None) -> Note:
        """Update the provided fields on a note; at least one must be given."""
        fields: dict[str, str] = {}

        if title is not None:
            title = title.strip()
            if not title:
                raise GuardrailViolation("Note title cannot be empty.")
            fields["title"] = title

        if content is not None:
            content = content.strip()
            if not content:
                raise GuardrailViolation("Note content cannot be empty.")
            fields["content"] = content

        if not fields:
            raise GuardrailViolation("At least one of title or content must be provided.")

        return self.repo.update(note_id, **fields)

    def delete_note(self, note_id: int) -> None:
        """Delete a note by id (raises RecordNotFoundError if missing)."""
        self.repo.delete(note_id)