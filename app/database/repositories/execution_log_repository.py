"""Repository for the ExecutionLog model."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.repository import BaseRepository
from app.models.execution_log import ExecutionLog


class ExecutionLogRepository(BaseRepository[ExecutionLog]):
    """Repository providing execution log-specific database operations."""

    DEFAULT_LIMIT = 100
    MAX_LIMIT = 500

    def __init__(self, db: Session) -> None:
        super().__init__(ExecutionLog, db)

    def get_by_workflow(self, workflow_id: str) -> list[ExecutionLog]:
        """Return all log entries for a workflow in chronological order."""

        stmt = (
            select(ExecutionLog)
            .where(ExecutionLog.workflow_id == workflow_id)
            .order_by(ExecutionLog.created_at.asc())
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_recent(
        self,
        limit: int = DEFAULT_LIMIT,
        level: str | None = None,
    ) -> list[ExecutionLog]:
        """Return recent log entries, optionally filtered by level."""

        limit = max(1, min(limit, self.MAX_LIMIT))

        stmt = select(ExecutionLog)

        if level:
            stmt = stmt.where(ExecutionLog.level == level.upper())

        stmt = (
            stmt
            .order_by(ExecutionLog.created_at.desc())
            .limit(limit)
        )

        return list(self.db.execute(stmt).scalars().all())