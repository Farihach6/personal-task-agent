"""API-level tests for the /api/v1/logs endpoint.

get_logging_service is overridden with an instance bound to the isolated
in-memory test database, so these tests never touch the real DB file.
"""

from app.api.logs_router import get_logging_service
from app.main import app
from app.services.logging_service import LoggingService


def _override_logging_service(workflow_session_factory) -> None:
    app.dependency_overrides[get_logging_service] = lambda: LoggingService(
        session_factory=workflow_session_factory
    )


def test_list_logs_returns_empty_when_none_exist(client, workflow_session_factory):
    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs")
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_list_logs_returns_newest_first(client, workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("First event", workflow_id="wf-1")
    service.log_event("Second event", workflow_id="wf-1")

    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs")
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["message"] for item in body["items"]] == ["Second event", "First event"]


def test_list_logs_filters_by_workflow_id(client, workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("For workflow 1", workflow_id="wf-1")
    service.log_event("For workflow 2", workflow_id="wf-2")

    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs", params={"workflow_id": "wf-1"})
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "For workflow 1"
    assert body["items"][0]["workflow_id"] == "wf-1"


def test_list_logs_filters_by_level(client, workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("Info event", level="INFO", workflow_id="wf-1")
    service.log_event("Error event", level="ERROR", workflow_id="wf-1")

    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs", params={"level": "ERROR"})
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["level"] == "ERROR"


def test_list_logs_filters_by_level_case_insensitively(client, workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("Warning event", level="WARNING", workflow_id="wf-1")

    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs", params={"level": "warning"})
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["level"] == "WARNING"


def test_list_logs_filters_by_workflow_id_and_level_combined(client, workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("wf-1 error", level="ERROR", workflow_id="wf-1")
    service.log_event("wf-1 info", level="INFO", workflow_id="wf-1")
    service.log_event("wf-2 error", level="ERROR", workflow_id="wf-2")

    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs", params={"workflow_id": "wf-1", "level": "ERROR"})
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "wf-1 error"


def test_list_logs_respects_limit(client, workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    for i in range(5):
        service.log_event(f"Event {i}", workflow_id="wf-1")

    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs", params={"limit": 2})
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    assert response.json()["total"] == 2


def test_list_logs_returns_empty_for_unknown_workflow_id(client, workflow_session_factory):
    service = LoggingService(session_factory=workflow_session_factory)
    service.log_event("Some event", workflow_id="wf-1")

    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs", params={"workflow_id": "nonexistent-id"})
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_list_logs_rejects_invalid_level(client, workflow_session_factory):
    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs", params={"level": "VERBOSE"})
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "guardrail_violation"
    assert "VERBOSE" in body["message"]


def test_list_logs_rejects_limit_below_minimum(client, workflow_session_factory):
    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs", params={"limit": 0})
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    assert response.status_code == 422


def test_list_logs_rejects_limit_above_maximum(client, workflow_session_factory):
    _override_logging_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/logs", params={"limit": 5000})
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    assert response.status_code == 422


def test_list_logs_handles_database_error_via_app_exception_handler(client):
    """If the underlying repository raises one of our own AppException
    subclasses (e.g. a database operation failure), it must map to a
    clean structured JSON error response rather than an unhandled crash."""
    from app.database.exceptions import DatabaseOperationError

    class _BoomLoggingService:
        def get_logs(self, workflow_id=None, level=None, limit=100):
            raise DatabaseOperationError("Could not query execution_logs.")

    app.dependency_overrides[get_logging_service] = lambda: _BoomLoggingService()
    try:
        response = client.get("/api/v1/logs")
    finally:
        app.dependency_overrides.pop(get_logging_service, None)

    assert response.status_code == 500
    body = response.json()
    assert body["error_code"] == "database_operation_error"
    assert "execution_logs" in body["message"]