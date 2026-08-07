"""Tests for WorkflowService, bound to the isolated in-memory test database
via the workflow_session_factory fixture rather than the real engine."""

import pytest

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


def test_complete_workflow_sets_completed_status_and_response(workflow_session_factory, db_session):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Find a restaurant")

    service.complete_workflow(workflow_id, final_response="Here are some options.")

    workflow = WorkflowRepository(db_session).get_by_id(workflow_id)
    assert workflow.status == "COMPLETED"
    assert workflow.final_response == "Here are some options."
    assert workflow.completed_at is not None


def test_fail_workflow_sets_failed_status(workflow_session_factory, db_session):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Find a restaurant")

    service.fail_workflow(workflow_id, final_response="Something went wrong.")

    workflow = WorkflowRepository(db_session).get_by_id(workflow_id)
    assert workflow.status == "FAILED"
    assert workflow.final_response == "Something went wrong."


def test_save_step_persists_action_summary_and_tool_details(workflow_session_factory, db_session):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Send an email")

    service.save_step(
        workflow_id=workflow_id,
        node_name="approval",
        action_summary="Human approved running tool 'email'.",
        tool_name="email",
        tool_input={"to": "john@example.com", "body": "hi"},
        tool_output=None,
    )

    steps = WorkflowStepRepository(db_session).get_by_workflow(workflow_id)
    assert len(steps) == 1
    assert steps[0].node_type == "APPROVAL"
    assert steps[0].tool_name == "email"


def test_save_step_defaults_node_name_case_insensitively(workflow_session_factory, db_session):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Hello")

    service.save_step(workflow_id=workflow_id, node_name="approval", action_summary="Approved.")

    steps = WorkflowStepRepository(db_session).get_by_workflow(workflow_id)
    assert steps[0].node_type == "APPROVAL"


def test_get_workflows_returns_newest_first_with_total(workflow_session_factory):
    service = WorkflowService(session_factory=workflow_session_factory)
    first_id = service.create_workflow("First request")
    second_id = service.create_workflow("Second request")
    service.complete_workflow(second_id, final_response="Done second.")
    service.complete_workflow(first_id, final_response="Done first.")

    items, total = service.get_workflows(limit=10, offset=0)

    assert total == 2
    # Newest first: second_id was created after first_id, so it has the
    # later started_at and must appear first regardless of completion order.
    assert [item["workflow_id"] for item in items] == [second_id, first_id]
    assert items[0]["user_input"] == "Second request"
    assert items[0]["final_response"] == "Done second."
    assert items[0]["status"] == "COMPLETED"


def test_get_workflows_respects_limit_and_offset(workflow_session_factory):
    service = WorkflowService(session_factory=workflow_session_factory)
    for i in range(5):
        service.create_workflow(f"Request {i}")

    page_one, total = service.get_workflows(limit=2, offset=0)
    page_two, _ = service.get_workflows(limit=2, offset=2)

    assert total == 5
    assert len(page_one) == 2
    assert len(page_two) == 2
    assert page_one[0]["workflow_id"] != page_two[0]["workflow_id"]


def test_get_workflow_returns_metadata_dict(workflow_session_factory):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Find a restaurant")
    service.complete_workflow(workflow_id, final_response="Here you go.")

    item = service.get_workflow(workflow_id)

    assert item["workflow_id"] == workflow_id
    assert item["user_input"] == "Find a restaurant"
    assert item["final_response"] == "Here you go."
    assert item["status"] == "COMPLETED"
    assert item["started_at"] is not None
    assert item["finished_at"] is not None


def test_get_workflow_raises_for_unknown_id(workflow_session_factory):
    from app.database.exceptions import RecordNotFoundError

    service = WorkflowService(session_factory=workflow_session_factory)
    with pytest.raises(RecordNotFoundError):
        service.get_workflow("nonexistent-id")


def test_get_workflow_steps_returns_chronological_normalized_steps(
    workflow_session_factory,
):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Send an email to john@example.com saying hi")

    service.record_step(
        workflow_id, "REASON", {"user_message": "Send an email"}, {"intent": "Send an email"}
    )
    service.record_step(
        workflow_id, "PLAN", {"intent": "Send an email"}, {"plan": ["Send the email"]}
    )
    service.record_step(
        workflow_id,
        "ACT",
        {"tool_name": "email", "tool_input": {"to": "john@example.com"}},
        {"tool_result": None, "status": "WAITING_APPROVAL"},
        tool_name="email",
    )
    service.save_step(
        workflow_id=workflow_id,
        node_name="approval",
        action_summary="Human approved running tool 'email'.",
        tool_name="email",
        tool_input={"to": "john@example.com"},
    )
    service.record_step(
        workflow_id,
        "ACT",
        {"tool_name": "email", "tool_input": {"to": "john@example.com"}},
        {"tool_result": {"sent": True}, "status": "RUNNING"},
        tool_name="email",
    )
    service.record_step(
        workflow_id,
        "OBSERVE",
        {"tool_result": {"sent": True}},
        {"final_response": "Sent!", "status": "COMPLETED"},
    )

    steps = service.get_workflow_steps(workflow_id)

    assert [s["node_name"] for s in steps] == ["REASON", "PLAN", "ACT", "APPROVAL", "ACT", "OBSERVE"]
    assert [s["sequence_number"] for s in steps] == [1, 2, 3, 4, 5, 6]
    assert steps[0]["action_summary"] == "Identified intent: Send an email"
    assert steps[1]["action_summary"] == "Generated a 1-step plan."
    assert steps[2]["action_summary"] == "Paused for approval before running tool 'email'."
    assert steps[3]["action_summary"] == "Human approved running tool 'email'."
    assert steps[3]["tool_name"] == "email"
    assert steps[4]["action_summary"] == "Executed tool 'email'."
    assert steps[4]["tool_output"] == {"sent": True}
    assert steps[5]["action_summary"] == "Generated the final response."


def test_get_workflow_steps_returns_empty_list_for_workflow_with_no_steps(
    workflow_session_factory,
):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Hello")

    assert service.get_workflow_steps(workflow_id) == []