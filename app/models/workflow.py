"""Workflow table: one row per user request handled by the agent."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Workflow(Base):
    """Represents a single end-to-end agent run for one user prompt."""

    __tablename__ = "workflows"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING','WAITING_APPROVAL','COMPLETED','FAILED')",
            name="ck_workflows_status",
        ),
        CheckConstraint(
            "approval_status IN ('NONE','PENDING','APPROVED','REJECTED')",
            name="ck_workflows_approval_status",
        ),
        Index("ix_workflows_status", "status"),
        Index("ix_workflows_started_at", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING")
    tools_used: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON-encoded list
    approval_required: Mapped[bool] = mapped_column(default=False)
    approval_status: Mapped[str] = mapped_column(String(16), nullable=False, default="NONE")
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", order_by="WorkflowStep.step_number"
    )
    logs: Mapped[list["ExecutionLog"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", order_by="ExecutionLog.created_at"
    )

    def __repr__(self) -> str:
        return f"<Workflow id={self.id} status={self.status}>"