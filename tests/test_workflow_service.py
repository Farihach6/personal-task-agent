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