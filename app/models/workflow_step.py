"""WorkflowStep table: the detailed Reason/Plan/Act/Observe trace of a workflow."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class WorkflowStep(Base):
    """Represents a single node execution within a workflow's agent graph."""

    __tablename__ = "workflow_steps"
    __table_args__ = (
        CheckConstraint(
            "node_type IN ('REASON','PLAN','ACT','OBSERVE','APPROVAL')",
            name="ck_workflow_steps_node_type",
        ),
        Index(
            "ix_workflow_steps_workflow_id_step_number",
            "workflow_id",
            "step_number",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflows.id"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    node_type: Mapped[str] = mapped_column(String(16), nullable=False)  # REASON, PLAN, ACT, OBSERVE, APPROVAL
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded
    output_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    workflow: Mapped["Workflow"] = relationship(back_populates="steps")

    def __repr__(self) -> str:
        return f"<WorkflowStep workflow_id={self.workflow_id} step={self.step_number} node={self.node_type}>"