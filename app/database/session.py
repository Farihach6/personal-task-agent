
"""Database engine and session management."""

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# check_same_thread=False is required for SQLite when used with FastAPI's
# threaded request handling.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,   # Recommended
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context-managed session for code running outside FastAPI requests."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
