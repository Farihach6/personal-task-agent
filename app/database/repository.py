"""Generic repository layer.

Provides reusable CRUD operations for SQLAlchemy ORM models.
All future services, tools, and LangGraph nodes should interact with the
database through repositories instead of directly using SQLAlchemy sessions.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.database.base import Base
from app.database.exceptions import (
    DatabaseOperationError,
    IntegrityConstraintError,
    RecordNotFoundError,
)

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic CRUD repository for SQLAlchemy models."""

    MAX_PAGE_SIZE = 500

    def __init__(self, model: type[ModelType], db: Session) -> None:
        self.model = model
        self.db = db

    def create(self, **fields: Any) -> ModelType:
        """Create and persist a new record."""
        instance = self.model(**fields)

        try:
            self.db.add(instance)
            self.db.commit()
            self.db.refresh(instance)

            logger.info(
                "Created %s (id=%s)",
                self.model.__name__,
                getattr(instance, "id", None),
            )

            return instance

        except IntegrityError as exc:
            self.db.rollback()

            raise IntegrityConstraintError(
                f"Failed to create {self.model.__name__}: {exc.orig}"
            ) from exc

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise DatabaseOperationError(
                f"Database error while creating {self.model.__name__}: {exc}"
            ) from exc

    def get_by_id(self, record_id: Any) -> ModelType:
        """Return a record by primary key or raise RecordNotFoundError."""
        instance = self.db.get(self.model, record_id)

        if instance is None:
            raise RecordNotFoundError(
                f"{self.model.__name__} with id '{record_id}' not found."
            )

        return instance

    def get_by_id_or_none(self, record_id: Any) -> ModelType | None:
        """Return a record or None if it does not exist."""
        return self.db.get(self.model, record_id)

    def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelType]:
        """Return paginated records."""

        limit = max(1, min(limit, self.MAX_PAGE_SIZE))
        offset = max(0, offset)

        stmt = (
            select(self.model)
            .offset(offset)
            .limit(limit)
        )

        return list(self.db.execute(stmt).scalars().all())

    def update(
        self,
        record_id: Any,
        **fields: Any,
    ) -> ModelType:
        """Update an existing record."""

        instance = self.get_by_id(record_id)

        try:
            for key, value in fields.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)

            self.db.commit()
            self.db.refresh(instance)

            logger.info(
                "Updated %s (id=%s)",
                self.model.__name__,
                record_id,
            )

            return instance

        except IntegrityError as exc:
            self.db.rollback()

            raise IntegrityConstraintError(
                f"Failed to update {self.model.__name__}: {exc.orig}"
            ) from exc

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise DatabaseOperationError(
                f"Database error while updating {self.model.__name__}: {exc}"
            ) from exc

    def delete(self, record_id: Any) -> bool:
        """Delete a record by primary key."""

        instance = self.get_by_id(record_id)

        try:
            self.db.delete(instance)
            self.db.commit()

            logger.info(
                "Deleted %s (id=%s)",
                self.model.__name__,
                record_id,
            )

            return True

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise DatabaseOperationError(
                f"Database error while deleting {self.model.__name__}: {exc}"
            ) from exc

    def count(self) -> int:
        """Return total number of records."""

        stmt = select(func.count()).select_from(self.model)
        return self.db.execute(stmt).scalar_one()

    def exists(self, record_id: Any) -> bool:
        """Check whether a record exists."""

        return self.db.get(self.model, record_id) is not None