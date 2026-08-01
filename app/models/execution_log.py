"""ExecutionLog table: chronological operational log entries for the dashboard."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ExecutionLog(Base):
    """Represents a single log entry, optionally tied to a workflow."""

    __tablename__ = "execution_logs"
    __table_args__ = (
        CheckConstraint("level IN ('INFO','WARNING','ERROR')", name="ck_execution_logs_level"),
        Index("ix_execution_logs_workflow_id_created_at", "workflow_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflows.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    workflow: Mapped["Workflow | None"] = relationship(back_populates="logs")

    def __repr__(self) -> str:
        return f"<ExecutionLog id={self.id} level={self.level}>"
