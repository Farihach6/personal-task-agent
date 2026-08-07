"""Tests for LoggingService, bound to the isolated in-memory test database
via the workflow_session_factory fixture rather than the real engine."""

from app.database.repositories import ExecutionLogRepository
from app.services.logging_service import LoggingService


def test_log_event_persists_a_row_with_expected_fields(workflow_session_factory, db_session):
    service = LoggingService(session_factory=workflow_session_factory)

    service.log_event("Workflow started: 'do the thing'", level="INFO", workflow_id="wf-1")

    logs = ExecutionLogRepository(db_session).get_by_workflow("wf-1")
    assert len(logs) == 1
    assert logs[0].level == "INFO"
    assert logs[0].message == "Workflow started: 'do the thing'"
    assert logs[0].workflow_id == "wf-1"
    assert logs[0].created_at is not None


def test_log_event_defaults_to_info_level(workflow_session_factory, db_session):
    service = LoggingService(session_factory=workflow_session_factory)

    service.log_event("Something happened", workflow_id="wf-1")

    logs = ExecutionLogRepository(db_session).get_by_workflow("wf-1")
    assert logs[0].level == "INFO"


def test_log_event_normalizes_lowercase_level_to_uppercase(workflow_session_factory, db_session):
    service = LoggingService(session_factory=workflow_session_factory)

    service.log_event("Tool failed", level="error", workflow_id="wf-1")

    logs = ExecutionLogRepository(db_session).get_by_workflow("wf-1")
    assert logs[0].level == "ERROR"


def test_log_event_falls_back_to_info_for_unrecognized_level(workflow_session_factory, db_session):
    service = LoggingService(session_factory=workflow_session_factory)

    service.log_event("Weird level", level="VERBOSE", workflow_id="wf-1")

    logs = ExecutionLogRepository(db_session).get_by_workflow("wf-1")
    assert logs[0].level == "INFO"


def test_log_event_allows_null_workflow_id_for_system_level_events(
    workflow_session_factory, db_session
):
    service = LoggingService(session_factory=workflow_session_factory)

    service.log_event("Application started", level="INFO", workflow_id=None)

    logs = ExecutionLogRepository(db_session).get_recent(limit=10)
    assert len(logs) == 1
    assert logs[0].workflow_id is None


def test_log_event_never_raises_when_persistence_fails():
    """A logging failure must never crash the caller. Passing a
    session_factory that always raises simulates a broken DB connection."""

    def _broken_session_factory():
        raise RuntimeError("database is unavailable")

    service = LoggingService(session_factory=_broken_session_factory)

    # Must not raise, even though persistence is impossible.
    service.log_event("This will fail to persist", level="ERROR", workflow_id="wf-1")


def test_get_logs_returns_newest_first(workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("First event", workflow_id="wf-1")
    service.log_event("Second event", workflow_id="wf-1")
    service.log_event("Third event", workflow_id="wf-1")

    logs = service.get_logs(workflow_id="wf-1")

    assert [log["message"] for log in logs] == ["Third event", "Second event", "First event"]


def test_get_logs_filters_by_workflow_id(workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("For workflow 1", workflow_id="wf-1")
    service.log_event("For workflow 2", workflow_id="wf-2")

    logs = service.get_logs(workflow_id="wf-1")

    assert len(logs) == 1
    assert logs[0]["message"] == "For workflow 1"


def test_get_logs_filters_by_level(workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("Info event", level="INFO", workflow_id="wf-1")
    service.log_event("Warning event", level="WARNING", workflow_id="wf-1")
    service.log_event("Error event", level="ERROR", workflow_id="wf-1")

    logs = service.get_logs(level="ERROR")

    assert len(logs) == 1
    assert logs[0]["message"] == "Error event"


def test_get_logs_filters_by_workflow_id_and_level_combined(workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("wf-1 error", level="ERROR", workflow_id="wf-1")
    service.log_event("wf-1 info", level="INFO", workflow_id="wf-1")
    service.log_event("wf-2 error", level="ERROR", workflow_id="wf-2")

    logs = service.get_logs(workflow_id="wf-1", level="ERROR")

    assert len(logs) == 1
    assert logs[0]["message"] == "wf-1 error"


def test_get_logs_respects_limit(workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    for i in range(5):
        service.log_event(f"Event {i}", workflow_id="wf-1")

    logs = service.get_logs(workflow_id="wf-1", limit=2)

    assert len(logs) == 2


def test_get_logs_returns_empty_list_when_no_logs_exist(workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)

    assert service.get_logs() == []


def test_get_logs_returns_empty_list_for_unknown_workflow_id(workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("Some event", workflow_id="wf-1")

    assert service.get_logs(workflow_id="nonexistent-workflow") == []