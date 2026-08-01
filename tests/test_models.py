"""Tests for model relationships, cascade behavior, and constraints."""

import pytest

from app.database.exceptions import IntegrityConstraintError
from app.database.repositories import (
    ExecutionLogRepository,
    WorkflowRepository,
    WorkflowStepRepository,
)


def test_workflow_step_cascade_delete(db_session):
    workflow_repo = WorkflowRepository(db_session)
    step_repo = WorkflowStepRepository(db_session)

    wf = workflow_repo.create(user_prompt="Summarize my day")
    step_repo.create(workflow_id=wf.id, step_number=1, node_type="REASON")
    step_repo.create(workflow_id=wf.id, step_number=2, node_type="PLAN")

    assert len(step_repo.get_by_workflow(wf.id)) == 2

    workflow_repo.delete(wf.id)

    assert step_repo.get_by_workflow(wf.id) == []


def test_execution_log_cascade_delete(db_session):
    workflow_repo = WorkflowRepository(db_session)
    log_repo = ExecutionLogRepository(db_session)

    wf = workflow_repo.create(user_prompt="Send an email")
    log_repo.create(workflow_id=wf.id, level="INFO", message="Started workflow")

    assert len(log_repo.get_by_workflow(wf.id)) == 1

    workflow_repo.delete(wf.id)

    assert log_repo.get_by_workflow(wf.id) == []


def test_workflow_status_check_constraint_rejects_invalid_value(db_session):
    workflow_repo = WorkflowRepository(db_session)
    with pytest.raises(IntegrityConstraintError):
        workflow_repo.create(user_prompt="Bad status", status="NOT_A_REAL_STATUS")


def test_workflow_step_unique_constraint_rejects_duplicate_step_number(db_session):
    workflow_repo = WorkflowRepository(db_session)
    step_repo = WorkflowStepRepository(db_session)

    wf = workflow_repo.create(user_prompt="Duplicate step test")
    step_repo.create(workflow_id=wf.id, step_number=1, node_type="REASON")

    with pytest.raises(IntegrityConstraintError):
        step_repo.create(workflow_id=wf.id, step_number=1, node_type="PLAN")


def test_get_next_step_number_increments_correctly(db_session):
    workflow_repo = WorkflowRepository(db_session)
    step_repo = WorkflowStepRepository(db_session)

    wf = workflow_repo.create(user_prompt="Step numbering test")
    assert step_repo.get_next_step_number(wf.id) == 1

    step_repo.create(workflow_id=wf.id, step_number=1, node_type="REASON")
    assert step_repo.get_next_step_number(wf.id) == 2


def test_workflow_recent_and_status_filters(db_session):
    workflow_repo = WorkflowRepository(db_session)
    workflow_repo.create(user_prompt="Running one", status="RUNNING")
    workflow_repo.create(user_prompt="Completed one", status="COMPLETED")

    running = workflow_repo.get_by_status("RUNNING")
    completed = workflow_repo.get_by_status("COMPLETED")

    assert len(running) == 1
    assert len(completed) == 1
    assert running[0].user_prompt == "Running one"