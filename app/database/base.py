"""SQLAlchemy declarative base and table initialization."""

from sqlalchemy.orm import DeclarativeBase

from app.core.logger import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Shared declarative base class for all ORM models."""


def init_db() -> None:
    """Create all tables that don't yet exist.

    Imports models locally to avoid circular imports (models import Base
    from this module).
    """
    from app.database.session import engine
    from app.models import (  # noqa: F401
        execution_log,
        note,
        workflow,
        workflow_step,
    )

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized.")
