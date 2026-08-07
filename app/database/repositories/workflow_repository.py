"""Repository for the Workflow model."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.repository import BaseRepository
from app.models.workflow import Workflow


class WorkflowRepository(BaseRepository[Workflow]):
    """Repository providing workflow-specific database operations."""

    DEFAULT_LIMIT = 50
    MAX_LIMIT = 500

    def __init__(self, db: Session) -> None:
        super().__init__(Workflow, db)

    def get_recent(
        self,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[Workflow]:
        """Return the most recently started workflows, newest first."""

        limit = max(1, min(limit, self.MAX_LIMIT))
        offset = max(0, offset)

        stmt = (
            select(Workflow)
            .order_by(Workflow.started_at.desc())
            .limit(limit)
            .offset(offset)
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_by_status(
        self,
        status: str,
        limit: int = DEFAULT_LIMIT,
    ) -> list[Workflow]:
        """Return workflows filtered by status."""

        limit = max(1, min(limit, self.MAX_LIMIT))

        stmt = (
            select(Workflow)
            .where(Workflow.status == status)
            .order_by(Workflow.started_at.desc())
            .limit(limit)
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_pending_approvals(self) -> list[Workflow]:
        """Return workflows waiting for human approval."""

        stmt = (
            select(Workflow)
            .where(Workflow.approval_status == "PENDING")
            .order_by(Workflow.started_at.desc())
        )

        return list(self.db.execute(stmt).scalars().all())