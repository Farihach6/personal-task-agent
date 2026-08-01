"""Workflow persistence service.

Wraps the Workflow/WorkflowStep repositories so the agent service can
persist a run's lifecycle (create -> per-node steps -> finalize) without
knowing about SQLAlchemy sessions directly. Uses a session_scope-style
context manager because agent runs happen outside FastAPI's per-request
session lifecycle (see architecture: session_scope() is reserved for
non-request code such as this).
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.database.repositories import WorkflowRepository, WorkflowStepRepository
from app.database.session import session_scope
from app.utils.serialization import to_json

logger = get_logger(__name__)


class WorkflowService:
    """Persists workflow lifecycle events (creation, steps, finalization)."""

    def __init__(
        self, session_factory: Callable[[], AbstractContextManager[Session]] = session_scope
    ) -> None:
        # Injectable so tests can bind this service to an isolated in-memory
        # database instead of the real configured engine.
        self._session_factory = session_factory

    def create_workflow(self, user_prompt: str) -> str:
        """Insert a new RUNNING workflow row and return its id."""
        with self._session_factory() as db:
            workflow = WorkflowRepository(db).create(user_prompt=user_prompt, status="RUNNING")
            workflow_id = workflow.id
        logger.info("Workflow created: workflow_id=%s", workflow_id)
        return workflow_id

    def record_step(
        self,
        workflow_id: str,
        node_type: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
    ) -> None:
        """Append a workflow_steps row for one node execution."""
        with self._session_factory() as db:
            step_repo = WorkflowStepRepository(db)
            step_number = step_repo.get_next_step_number(workflow_id)
            step_repo.create(
                workflow_id=workflow_id,
                step_number=step_number,
                node_type=node_type,
                input_data=to_json(input_data),
                output_data=to_json(output_data),
            )
        logger.info(
            "Workflow step recorded: workflow_id=%s node_type=%s step_number=%s",
            workflow_id,
            node_type,
            step_number,
        )

    def finalize_workflow(
        self,
        workflow_id: str,
        status: str,
        final_response: str | None = None,
        tools_used: list[str] | None = None,
    ) -> None:
        """Mark a workflow as COMPLETED/FAILED and record its final response."""
        with self._session_factory() as db:
            repo = WorkflowRepository(db)
            workflow = repo.get_by_id(workflow_id)
    
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - workflow.started_at).total_seconds() * 1000)
            repo.update(
                workflow_id,
                status=status,
                final_response=final_response,
                completed_at=completed_at,
                duration_ms=duration_ms,
                tools_used=to_json(tools_used or []),
            )
        logger.info("Workflow finalized: workflow_id=%s status=%s", workflow_id, status)