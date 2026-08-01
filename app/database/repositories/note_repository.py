"""Repository for the Note model."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database.repository import BaseRepository
from app.models.note import Note


class NoteRepository(BaseRepository[Note]):
    """Repository providing note-specific database operations."""

    DEFAULT_LIMIT = 50
    MAX_LIMIT = 500

    def __init__(self, db: Session) -> None:
        super().__init__(Note, db)

    def search(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[Note]:
        """Search notes by title or content with pagination."""

        limit = max(1, min(limit, self.MAX_LIMIT))
        offset = max(0, offset)
        query = query.strip()

        if not query:
            return []

        pattern = f"%{query}%"

        stmt = (
            select(Note)
            .where(
                or_(
                    Note.title.ilike(pattern),
                    Note.content.ilike(pattern),
                )
            )
            .order_by(Note.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )

        return list(self.db.execute(stmt).scalars().all())

    def count_search(self, query: str) -> int:
        """Return number of notes matching search."""

        query = query.strip()

        if not query:
            return 0

        pattern = f"%{query}%"

        stmt = (
            select(func.count())
            .select_from(Note)
            .where(
                or_(
                    Note.title.ilike(pattern),
                    Note.content.ilike(pattern),
                )
            )
        )

        return self.db.execute(stmt).scalar_one()

    def get_all_ordered(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Note]:
        """Return notes ordered by most recently updated."""

        limit = max(1, min(limit, self.MAX_LIMIT))
        offset = max(0, offset)

        stmt = (
            select(Note)
            .order_by(Note.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )

        return list(self.db.execute(stmt).scalars().all())