"""Workflow persistence service.

Wraps the Workflow/WorkflowStep repositories so the agent service can
persist a run's lifecycle (create -> per-node steps -> finalize) without
knowing about SQLAlchemy sessions directly. Uses a session_scope-style
context manager because agent runs happen outside FastAPI's per-request
session lifecycle (see architecture: session_scope() is reserved for
non-request code such as this).

Also supports the human-approval flow: pausing a workflow
(mark_awaiting_approval), listing paused workflows (get_pending_approvals),
and reconstructing enough context to resume one (get_workflow_context) —
entirely from data already persisted in workflows/workflow_steps, so no
separate approval-state store is needed.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.database.repositories import WorkflowRepository, WorkflowStepRepository
from app.database.session import session_scope
from app.utils.serialization import from_json, to_json

logger = get_logger(__name__)


class WorkflowService:
    """Persists workflow lifecycle events (creation, steps, finalization, approvals)."""

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
        tool_name: str | None = None,
    ) -> None:
        """Append a workflow_steps row for one node execution."""
        with self._session_factory() as db:
            step_repo = WorkflowStepRepository(db)
            step_number = step_repo.get_next_step_number(workflow_id)
            step_repo.create(
                workflow_id=workflow_id,
                step_number=step_number,
                node_type=node_type,
                tool_name=tool_name,
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
        approval_status: str | None = None,
    ) -> None:
        """Mark a workflow as COMPLETED/FAILED and record its final response.

        `approval_status` is optional and only updated when explicitly
        passed (e.g. "APPROVED"/"REJECTED" when finalizing after a resume),
        so ordinary non-approval workflows are unaffected.
        """
        with self._session_factory() as db:
            repo = WorkflowRepository(db)
            workflow = repo.get_by_id(workflow_id)
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - workflow.started_at).total_seconds() * 1000)
            update_fields: dict[str, Any] = {
                "status": status,
                "final_response": final_response,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "tools_used": to_json(tools_used or []),
            }
            if approval_status is not None:
                update_fields["approval_status"] = approval_status
            repo.update(workflow_id, **update_fields)
        logger.info("Workflow finalized: workflow_id=%s status=%s", workflow_id, status)

    def mark_awaiting_approval(self, workflow_id: str) -> None:
        """Pause a workflow, marking it as waiting on a human approval decision.

        Deliberately does not touch completed_at/duration_ms — the workflow
        isn't finished, just paused.
        """
        with self._session_factory() as db:
            WorkflowRepository(db).update(
                workflow_id,
                status="WAITING_APPROVAL",
                approval_required=True,
                approval_status="PENDING",
            )
        logger.info("Workflow marked WAITING_APPROVAL: workflow_id=%s", workflow_id)

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Return a plain-dict summary of every workflow awaiting approval,
        including the tool/action it paused on (read back from its ACT step)."""
        with self._session_factory() as db:
            workflows = WorkflowRepository(db).get_pending_approvals()
            step_repo = WorkflowStepRepository(db)

            summaries: list[dict[str, Any]] = []
            for wf in workflows:
                act_steps = [s for s in step_repo.get_by_workflow(wf.id) if s.node_type == "ACT"]
                tool_name = None
                tool_input: dict[str, Any] = {}
                if act_steps:
                    input_data = from_json(act_steps[-1].input_data, default={})
                    tool_name = input_data.get("tool_name")
                    tool_input = input_data.get("tool_input") or {}
                summaries.append(
                    {
                        "workflow_id": wf.id,
                        "user_prompt": wf.user_prompt,
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "created_at": wf.started_at,
                    }
                )
            return summaries

    def get_workflow_context(self, workflow_id: str) -> dict[str, Any]:
        """Reconstruct enough context (user_message, intent, plan, tool_name,
        tool_input) to resume a paused workflow — read back entirely from
        the already-persisted workflow row and workflow_steps, so no
        separate duplicate state has to be kept anywhere in memory.
        """
        with self._session_factory() as db:
            workflow = WorkflowRepository(db).get_by_id(workflow_id)
            steps = WorkflowStepRepository(db).get_by_workflow(workflow_id)

            context: dict[str, Any] = {
                "user_message": workflow.user_prompt,
                "status": workflow.status,
                "approval_status": workflow.approval_status,
                "intent": "",
                "plan": [],
                "tool_name": None,
                "tool_input": None,
            }
            for step in steps:
                output_data = from_json(step.output_data, default={})
                input_data = from_json(step.input_data, default={})
                if step.node_type == "REASON":
                    context["intent"] = output_data.get("intent", "")
                elif step.node_type == "PLAN":
                    context["plan"] = output_data.get("plan", [])
                elif step.node_type == "ACT":
                    context["tool_name"] = input_data.get("tool_name")
                    context["tool_input"] = input_data.get("tool_input")

            return context

    # --- Milestone 9: workflow history persistence & retrieval ---
    #
    # complete_workflow()/fail_workflow() are thin, explicitly-named
    # wrappers around the existing finalize_workflow() — kept as separate
    # methods (rather than replacing finalize_workflow, which AgentService
    # already depends on) so both the original and the newly-requested
    # public interface work side by side without changing prior behavior.

    def complete_workflow(self, workflow_id: str, final_response: str | None = None) -> None:
        """Mark a workflow as successfully COMPLETED."""
        self.finalize_workflow(workflow_id, status="COMPLETED", final_response=final_response)

    def fail_workflow(self, workflow_id: str, final_response: str | None = None) -> None:
        """Mark a workflow as FAILED."""
        self.finalize_workflow(workflow_id, status="FAILED", final_response=final_response)

    def save_step(
        self,
        workflow_id: str,
        node_name: str,
        action_summary: str,
        tool_name: str | None = None,
        tool_input: dict[str, Any] | None = None,
        tool_output: dict[str, Any] | None = None,
    ) -> None:
        """Append a workflow_steps row with an explicit action_summary and
        tool input/output — a convenience entry point alongside record_step()
        for callers (e.g. the approval decision itself) that want this exact
        shape rather than record_step()'s more free-form input/output dicts.
        """
        self.record_step(
            workflow_id=workflow_id,
            node_type=node_name.upper(),
            input_data={"tool_name": tool_name, "tool_input": tool_input},
            output_data={"action_summary": action_summary, "tool_output": tool_output},
            tool_name=tool_name,
        )

    def get_workflows(self, limit: int = 50, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        """Return a page of workflows (newest first) plus the total count."""
        with self._session_factory() as db:
            repo = WorkflowRepository(db)
            workflows = repo.get_recent(limit=limit, offset=offset)
            total = repo.count()
            items = [self._workflow_to_dict(wf) for wf in workflows]
            return items, total

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Return a single workflow's metadata as a plain dict.

        Raises:
            RecordNotFoundError: if no workflow with this id exists.
        """
        with self._session_factory() as db:
            workflow = WorkflowRepository(db).get_by_id(workflow_id)
            return self._workflow_to_dict(workflow)

    def get_workflow_steps(self, workflow_id: str) -> list[dict[str, Any]]:
        """Return every step of a workflow, in chronological order, as plain dicts."""
        with self._session_factory() as db:
            steps = WorkflowStepRepository(db).get_by_workflow(workflow_id)
            return [self._step_to_dict(step) for step in steps]

    @staticmethod
    def _workflow_to_dict(workflow: Any) -> dict[str, Any]:
        """Convert a Workflow ORM row to a plain dict while its session is
        still open (attributes become unsafe to access once the enclosing
        `with self._session_factory()` block exits)."""
        return {
            "workflow_id": workflow.id,
            "user_input": workflow.user_prompt,
            "final_response": workflow.final_response,
            "status": workflow.status,
            "started_at": workflow.started_at,
            "finished_at": workflow.completed_at,
        }

    @staticmethod
    def _step_to_dict(step: Any) -> dict[str, Any]:
        """Convert a WorkflowStep ORM row to a plain dict, normalizing the
        two shapes that end up in input_data/output_data: the original
        per-node shape written by record_step() (Milestones 5-8) and the
        explicit action_summary/tool_output shape written by save_step()
        (Milestone 9's APPROVAL steps) — so API consumers see one
        consistent shape regardless of which method wrote the row.
        """
        input_data = from_json(step.input_data, default={})
        output_data = from_json(step.output_data, default={})

        if step.node_type == "REASON":
            action_summary = f"Identified intent: {output_data.get('intent', '')}".strip()
            tool_name, tool_input, tool_output = None, None, None
        elif step.node_type == "PLAN":
            plan = output_data.get("plan", [])
            action_summary = f"Generated a {len(plan)}-step plan."
            tool_name, tool_input, tool_output = None, None, None
        elif step.node_type == "ACT":
            tool_name = step.tool_name or input_data.get("tool_name")
            tool_input = input_data.get("tool_input")
            tool_output = output_data.get("tool_result")
            action_summary = (
                f"Paused for approval before running tool '{tool_name}'."
                if output_data.get("status") == "WAITING_APPROVAL"
                else f"Executed tool '{tool_name}'."
            )
        elif step.node_type == "OBSERVE":
            action_summary = "Generated the final response."
            tool_name, tool_input, tool_output = None, None, None
        elif step.node_type == "APPROVAL":
            action_summary = output_data.get("action_summary", "")
            tool_name = step.tool_name or input_data.get("tool_name")
            tool_input = input_data.get("tool_input")
            tool_output = output_data.get("tool_output")
        else:
            action_summary = ""
            tool_name, tool_input, tool_output = step.tool_name, None, None

        return {
            "workflow_id": step.workflow_id,
            "sequence_number": step.step_number,
            "node_name": step.node_type,
            "action_summary": action_summary,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "timestamp": step.created_at,
        }