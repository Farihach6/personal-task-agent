"""API-level tests for the /api/v1/approvals endpoints.

Both get_agent_service and get_workflow_service are overridden with
instances bound to the isolated in-memory test database, so these tests
never touch the real DB file or the real Groq/SMTP services.
"""

from app.agent.tools.email_tool import EmailTool
from app.agent.tools.search_tool import SearchTool
from app.agent.tools.tool_executor import ToolExecutor
from app.api.approvals_router import get_workflow_service
from app.core.exceptions import ExternalServiceError
from app.database.repositories import WorkflowRepository
from app.main import app
from app.services.agent_service import AgentService, get_agent_service
from app.services.workflow_service import WorkflowService


class _QueuedLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def generate(self, prompt: str) -> str:
        return self._responses.pop(0)


class _FakeEmailService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send_email(self, to: str, subject: str, body: str) -> dict:
        self.calls.append({"to": to, "subject": subject, "body": body})
        return {"sent": True, "simulated": False, "to": to, "subject": subject, "body": body,}


def _override_workflow_service(workflow_session_factory) -> None:
    app.dependency_overrides[get_workflow_service] = lambda: WorkflowService(
        session_factory=workflow_session_factory
    )


def test_list_pending_approvals_returns_empty_when_none_pending(client, workflow_session_factory):
    _override_workflow_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/approvals")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_list_pending_approvals_returns_paused_workflow(client, workflow_session_factory):
    workflow_service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = workflow_service.create_workflow("Send an email to john@example.com saying hi")
    workflow_service.record_step(
        workflow_id,
        "ACT",
        {"tool_name": "email", "tool_input": {"to": "john@example.com", "body": "hi"}},
        {"tool_result": None, "status": "WAITING_APPROVAL"},
    )
    workflow_service.mark_awaiting_approval(workflow_id)

    _override_workflow_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/approvals")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["workflow_id"] == workflow_id
    assert body["items"][0]["tool_name"] == "email"
    assert body["items"][0]["tool_input"] == {"to": "john@example.com", "body": "hi"}


def test_approve_unknown_workflow_returns_404(client):
    response = client.post("/api/v1/approvals/nonexistent-id/approve")
    assert response.status_code == 404


def test_reject_unknown_workflow_returns_404(client):
    response = client.post("/api/v1/approvals/nonexistent-id/reject")
    assert response.status_code == 404


def test_full_approval_lifecycle_via_http_send_list_approve(
    client, workflow_session_factory, db_session
):
    """End-to-end: POST /chat (pauses) -> GET /approvals (lists it) ->
    POST /approvals/{id}/approve (resumes and actually sends the email)."""
    fake_email_service = _FakeEmailService()
    tool_executor = ToolExecutor(
        tools=[SearchTool(), EmailTool(email_service=fake_email_service)]
    )
    workflow_service = WorkflowService(session_factory=workflow_session_factory)

    pause_llm = _QueuedLLMClient(["Send an email", '["Send the email"]'])
    pause_agent_service = AgentService(
        llm_client=pause_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )

    app.dependency_overrides[get_agent_service] = lambda: pause_agent_service
    try:
        chat_response = client.post(
            "/api/v1/chat",
            json={"message": "Send an email to john@example.com saying the meeting is at 3pm"},
        )
    finally:
        app.dependency_overrides.pop(get_agent_service, None)

    assert chat_response.status_code == 200
    chat_body = chat_response.json()
    assert chat_body["status"] == "WAITING_APPROVAL"
    workflow_id = chat_body["workflow_id"]

    _override_workflow_service(workflow_session_factory)
    try:
        list_response = client.get("/api/v1/approvals")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["workflow_id"] == workflow_id

    resume_llm = _QueuedLLMClient(["I've sent your email."])
    resume_agent_service = AgentService(
        llm_client=resume_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )

    app.dependency_overrides[get_agent_service] = lambda: resume_agent_service
    try:
        approve_response = client.post(f"/api/v1/approvals/{workflow_id}/approve")
    finally:
        app.dependency_overrides.pop(get_agent_service, None)

    assert approve_response.status_code == 200
    approve_body = approve_response.json()
    assert approve_body["status"] == "COMPLETED"
    assert approve_body["final_response"] == "I've sent your email."
    assert fake_email_service.calls == [
        {
            "to": "john@example.com",
            "subject": "Send an email",
            "body": "the meeting is at 3pm",
        }
    ]

    workflow = WorkflowRepository(db_session).get_by_id(workflow_id)
    assert workflow.status == "COMPLETED"
    assert workflow.approval_status == "APPROVED"


def test_full_approval_lifecycle_via_http_send_list_reject(
    client, workflow_session_factory, db_session
):
    """End-to-end: POST /chat (pauses) -> POST /approvals/{id}/reject
    completes the workflow gracefully without ever sending the email."""
    fake_email_service = _FakeEmailService()
    tool_executor = ToolExecutor(
        tools=[SearchTool(), EmailTool(email_service=fake_email_service)]
    )
    workflow_service = WorkflowService(session_factory=workflow_session_factory)

    pause_llm = _QueuedLLMClient(["Send an email", '["Send the email"]'])
    pause_agent_service = AgentService(
        llm_client=pause_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )

    app.dependency_overrides[get_agent_service] = lambda: pause_agent_service
    try:
        chat_response = client.post(
            "/api/v1/chat",
            json={"message": "Send an email to jane@example.com saying hello"},
        )
    finally:
        app.dependency_overrides.pop(get_agent_service, None)

    workflow_id = chat_response.json()["workflow_id"]

    reject_llm = _QueuedLLMClient(["Okay, I won't send that email."])
    reject_agent_service = AgentService(
        llm_client=reject_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )

    app.dependency_overrides[get_agent_service] = lambda: reject_agent_service
    try:
        reject_response = client.post(f"/api/v1/approvals/{workflow_id}/reject")
    finally:
        app.dependency_overrides.pop(get_agent_service, None)

    assert reject_response.status_code == 200
    reject_body = reject_response.json()
    assert reject_body["status"] == "COMPLETED"
    assert reject_body["final_response"] == "Okay, I won't send that email."
    assert fake_email_service.calls == []

    workflow = WorkflowRepository(db_session).get_by_id(workflow_id)
    assert workflow.approval_status == "REJECTED"

    _override_workflow_service(workflow_session_factory)
    try:
        list_response = client.get("/api/v1/approvals")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert list_response.json()["total"] == 0


def test_approve_when_email_service_raises_still_completes_gracefully_not_500(
    client, workflow_session_factory, db_session
):
    """A real SMTP-style failure during approve must surface as a clean
    200 with status FAILED (per the architecture's 'tool failures never
    crash the graph' principle), not an unhandled 500."""

    class _BoomEmailService:
        def send_email(self, to, subject, body):
            raise ExternalServiceError("SMTP connection refused")

    tool_executor = ToolExecutor(tools=[SearchTool(), EmailTool(email_service=_BoomEmailService())])
    workflow_service = WorkflowService(session_factory=workflow_session_factory)

    pause_llm = _QueuedLLMClient(["Send an email", '["Send the email"]'])
    pause_agent_service = AgentService(
        llm_client=pause_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    app.dependency_overrides[get_agent_service] = lambda: pause_agent_service
    try:
        chat_response = client.post(
            "/api/v1/chat",
            json={"message": "Send an email to john@example.com saying hi"},
        )
    finally:
        app.dependency_overrides.pop(get_agent_service, None)
    workflow_id = chat_response.json()["workflow_id"]

    resume_llm = _QueuedLLMClient(["I couldn't send that email."])
    resume_agent_service = AgentService(
        llm_client=resume_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    app.dependency_overrides[get_agent_service] = lambda: resume_agent_service
    try:
        approve_response = client.post(f"/api/v1/approvals/{workflow_id}/approve")
    finally:
        app.dependency_overrides.pop(get_agent_service, None)

    assert approve_response.status_code == 200
    body = approve_response.json()
    assert body["status"] == "FAILED"

    workflow = WorkflowRepository(db_session).get_by_id(workflow_id)
    assert workflow.status == "FAILED"
    assert workflow.approval_status == "APPROVED"  # the decision itself succeeded


def test_approve_twice_via_http_returns_400_and_does_not_resend(
    client, workflow_session_factory, db_session
):
    """Regression (idempotency guard): approving the same workflow twice
    over HTTP must not send the email a second time."""
    fake_email_service = _FakeEmailService()
    tool_executor = ToolExecutor(
        tools=[SearchTool(), EmailTool(email_service=fake_email_service)]
    )
    workflow_service = WorkflowService(session_factory=workflow_session_factory)

    pause_llm = _QueuedLLMClient(["Send an email", '["Send the email"]'])
    pause_agent_service = AgentService(
        llm_client=pause_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    app.dependency_overrides[get_agent_service] = lambda: pause_agent_service
    try:
        chat_response = client.post(
            "/api/v1/chat",
            json={"message": "Send an email to john@example.com saying hi"},
        )
    finally:
        app.dependency_overrides.pop(get_agent_service, None)
    workflow_id = chat_response.json()["workflow_id"]

    first_llm = _QueuedLLMClient(["Sent once."])
    first_agent_service = AgentService(
        llm_client=first_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    app.dependency_overrides[get_agent_service] = lambda: first_agent_service
    try:
        first_response = client.post(f"/api/v1/approvals/{workflow_id}/approve")
    finally:
        app.dependency_overrides.pop(get_agent_service, None)
    assert first_response.status_code == 200
    assert len(fake_email_service.calls) == 1

    second_llm = _QueuedLLMClient(["Sent again?!"])
    second_agent_service = AgentService(
        llm_client=second_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    app.dependency_overrides[get_agent_service] = lambda: second_agent_service
    try:
        second_response = client.post(f"/api/v1/approvals/{workflow_id}/approve")
    finally:
        app.dependency_overrides.pop(get_agent_service, None)

    assert second_response.status_code == 400
    assert len(fake_email_service.calls) == 1  # still only sent once