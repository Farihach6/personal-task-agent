"""Note table: user notes managed by the Notes tool/dashboard."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Note(Base):
    """Represents a single saved note."""

    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_title", "title"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Note id={self.id} title={self.title!r}>"