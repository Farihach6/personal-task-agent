"""Tests for WorkflowService, bound to the isolated in-memory test database
via the workflow_session_factory fixture rather than the real engine."""

from app.database.repositories import WorkflowRepository, WorkflowStepRepository
from app.services.workflow_service import WorkflowService


def test_create_workflow_persists_running_row(workflow_session_factory, db_session):
    service = WorkflowService(session_factory=workflow_session_factory)

    workflow_id = service.create_workflow("Book a flight to Paris")

    workflow = WorkflowRepository(db_session).get_by_id(workflow_id)
    assert workflow.user_prompt == "Book a flight to Paris"
    assert workflow.status == "RUNNING"
    assert workflow.approval_status == "NONE"


def test_record_step_appends_workflow_step_with_incrementing_numbers(
    workflow_session_factory, db_session
):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Order dinner")

    service.record_step(workflow_id, "REASON", {"user_message": "Order dinner"}, {"intent": "Order food"})
    service.record_step(
        workflow_id, "PLAN", {"intent": "Order food"}, {"plan": ["Pick restaurant", "Place order"]}
    )

    steps = WorkflowStepRepository(db_session).get_by_workflow(workflow_id)
    assert [s.node_type for s in steps] == ["REASON", "PLAN"]
    assert [s.step_number for s in steps] == [1, 2]


def test_record_step_serializes_input_and_output_as_json(workflow_session_factory, db_session):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Hello")

    service.record_step(workflow_id, "REASON", {"user_message": "Hello"}, {"intent": "Greet"})

    step = WorkflowStepRepository(db_session).get_by_workflow(workflow_id)[0]
    assert step.input_data == '{"user_message": "Hello"}'
    assert step.output_data == '{"intent": "Greet"}'


def test_finalize_workflow_updates_status_and_duration(workflow_session_factory, db_session):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Hello")

    service.finalize_workflow(workflow_id, status="COMPLETED")

    workflow = WorkflowRepository(db_session).get_by_id(workflow_id)
    assert workflow.status == "COMPLETED"
    assert workflow.completed_at is not None
    assert workflow.duration_ms is not None
    assert workflow.duration_ms >= 0


def test_finalize_workflow_can_mark_failed(workflow_session_factory, db_session):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Hello")

    service.finalize_workflow(workflow_id, status="FAILED")

    workflow = WorkflowRepository(db_session).get_by_id(workflow_id)
    assert workflow.status == "FAILED"


def test_finalize_workflow_can_set_approval_status(workflow_session_factory, db_session):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Send an email")

    service.finalize_workflow(workflow_id, status="COMPLETED", approval_status="APPROVED")

    workflow = WorkflowRepository(db_session).get_by_id(workflow_id)
    assert workflow.approval_status == "APPROVED"


def test_mark_awaiting_approval_updates_status_and_flags(workflow_session_factory, db_session):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Send an email to john@example.com")

    service.mark_awaiting_approval(workflow_id)

    workflow = WorkflowRepository(db_session).get_by_id(workflow_id)
    assert workflow.status == "WAITING_APPROVAL"
    assert workflow.approval_required is True
    assert workflow.approval_status == "PENDING"
    # A paused workflow is not finished yet.
    assert workflow.completed_at is None


def test_get_pending_approvals_returns_paused_workflow_with_tool_context(
    workflow_session_factory, db_session
):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Send an email to john@example.com saying hi")
    service.record_step(
        workflow_id,
        "REASON",
        {"user_message": "Send an email to john@example.com saying hi"},
        {"intent": "Send email"},
    )
    service.record_step(
        workflow_id,
        "PLAN",
        {"intent": "Send email"},
        {"plan": ["Send the email"]},
    )
    service.record_step(
        workflow_id,
        "ACT",
        {"tool_name": "email", "tool_input": {"to": "john@example.com", "body": "hi"}},
        {"tool_result": None, "status": "WAITING_APPROVAL"},
    )
    service.mark_awaiting_approval(workflow_id)

    pending = service.get_pending_approvals()

    assert len(pending) == 1
    assert pending[0]["workflow_id"] == workflow_id
    assert pending[0]["tool_name"] == "email"
    assert pending[0]["tool_input"] == {"to": "john@example.com", "body": "hi"}


def test_get_pending_approvals_excludes_non_paused_workflows(workflow_session_factory):
    service = WorkflowService(session_factory=workflow_session_factory)
    running_id = service.create_workflow("Find a restaurant")
    service.finalize_workflow(running_id, status="COMPLETED", final_response="Done.")

    assert service.get_pending_approvals() == []


def test_get_workflow_context_reconstructs_intent_plan_and_tool_call(
    workflow_session_factory,
):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Send an email to john@example.com saying hi")
    service.record_step(
        workflow_id,
        "REASON",
        {"user_message": "Send an email to john@example.com saying hi"},
        {"intent": "Send email"},
    )
    service.record_step(workflow_id, "PLAN", {"intent": "Send email"}, {"plan": ["Send the email"]})
    service.record_step(
        workflow_id,
        "ACT",
        {"tool_name": "email", "tool_input": {"to": "john@example.com", "body": "hi"}},
        {"tool_result": None, "status": "WAITING_APPROVAL"},
    )
    service.mark_awaiting_approval(workflow_id)

    context = service.get_workflow_context(workflow_id)

    assert context["user_message"] == "Send an email to john@example.com saying hi"
    assert context["intent"] == "Send email"
    assert context["plan"] == ["Send the email"]
    assert context["tool_name"] == "email"
    assert context["tool_input"] == {"to": "john@example.com", "body": "hi"}
    assert context["approval_status"] == "PENDING"
    assert context["status"] == "WAITING_APPROVAL"


def test_get_workflow_context_returns_safe_defaults_when_no_steps_recorded(
    workflow_session_factory,
):
    """A freshly created workflow with zero workflow_steps rows must still
    return a usable context rather than raising."""
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Hello")

    context = service.get_workflow_context(workflow_id)

    assert context["user_message"] == "Hello"
    assert context["status"] == "RUNNING"
    assert context["intent"] == ""
    assert context["plan"] == []
    assert context["tool_name"] is None
    assert context["tool_input"] is None