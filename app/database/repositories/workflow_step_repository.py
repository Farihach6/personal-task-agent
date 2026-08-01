"""Repository for the WorkflowStep model."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.repository import BaseRepository
from app.models.workflow_step import WorkflowStep


class WorkflowStepRepository(BaseRepository[WorkflowStep]):
    """Repository providing workflow step-specific database operations."""

    def __init__(self, db: Session) -> None:
        super().__init__(WorkflowStep, db)

    def get_by_workflow(self, workflow_id: str) -> list[WorkflowStep]:
        """Return all steps for a workflow ordered by step number."""

        stmt = (
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == workflow_id)
            .order_by(WorkflowStep.step_number.asc())
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_next_step_number(self, workflow_id: str) -> int:
        """Return the next available step number for a workflow."""

        stmt = (
            select(func.max(WorkflowStep.step_number))
            .where(WorkflowStep.workflow_id == workflow_id)
        )

        last_step = self.db.execute(stmt).scalar_one()

        return 1 if last_step is None else last_step + 1