"""API-level tests for the /api/v1/workflows endpoints.

get_workflow_service is overridden with an instance bound to the isolated
in-memory test database, so these tests never touch the real DB file.
"""

from app.agent.tools.email_tool import EmailTool
from app.agent.tools.search_tool import SearchTool
from app.agent.tools.tool_executor import ToolExecutor
from app.api.approvals_router import get_workflow_service
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
        return {"sent": True, "simulated": False, "to": to, "subject": subject}


def _override_workflow_service(workflow_session_factory) -> None:
    app.dependency_overrides[get_workflow_service] = lambda: WorkflowService(
        session_factory=workflow_session_factory
    )


def test_list_workflows_returns_empty_when_none_exist(client, workflow_session_factory):
    _override_workflow_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/workflows")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_list_workflows_returns_newest_first(client, workflow_session_factory):
    service = WorkflowService(session_factory=workflow_session_factory)
    first_id = service.create_workflow("First request")
    second_id = service.create_workflow("Second request")
    service.complete_workflow(first_id, final_response="Done first.")
    service.complete_workflow(second_id, final_response="Done second.")

    _override_workflow_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/workflows")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    # Newest first: second_id was created after first_id.
    assert [item["workflow_id"] for item in body["items"]] == [second_id, first_id]


def test_get_workflow_returns_metadata(client, workflow_session_factory):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Find a restaurant")
    service.complete_workflow(workflow_id, final_response="Here you go.")

    _override_workflow_service(workflow_session_factory)
    try:
        response = client.get(f"/api/v1/workflows/{workflow_id}")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == workflow_id
    assert body["user_input"] == "Find a restaurant"
    assert body["final_response"] == "Here you go."
    assert body["status"] == "COMPLETED"


def test_get_workflow_not_found_returns_404(client, workflow_session_factory):
    _override_workflow_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/workflows/nonexistent-id")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert response.status_code == 404


def test_get_workflow_steps_returns_chronological_steps(client, workflow_session_factory):
    service = WorkflowService(session_factory=workflow_session_factory)
    workflow_id = service.create_workflow("Find a restaurant")
    service.record_step(workflow_id, "REASON", {"user_message": "Find a restaurant"}, {"intent": "Find food"})
    service.record_step(workflow_id, "PLAN", {"intent": "Find food"}, {"plan": ["Search restaurants"]})

    _override_workflow_service(workflow_session_factory)
    try:
        response = client.get(f"/api/v1/workflows/{workflow_id}/steps")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["node_name"] for item in body["items"]] == ["REASON", "PLAN"]
    assert body["items"][0]["sequence_number"] == 1
    assert body["items"][1]["sequence_number"] == 2


def test_get_workflow_steps_returns_empty_for_unknown_workflow(client, workflow_session_factory):
    """An unknown workflow_id has no steps rather than a 404 — the steps
    endpoint doesn't itself validate the parent workflow exists, matching
    get_workflow_steps()'s pure read-back-what-exists behavior."""
    _override_workflow_service(workflow_session_factory)
    try:
        response = client.get("/api/v1/workflows/nonexistent-id/steps")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_full_chat_to_history_end_to_end(client, workflow_session_factory, db_session):
    """End-to-end: POST /chat runs Reason->Plan->Act->Observe (Search path)
    -> GET /workflows lists it -> GET /workflows/{id}/steps shows all four
    recorded steps in order."""
    llm = _QueuedLLMClient(["Find restaurants", '["Search restaurants"]', "Here are some options."])
    workflow_service = WorkflowService(session_factory=workflow_session_factory)
    tool_executor = ToolExecutor(tools=[SearchTool()])
    agent_service = AgentService(
        llm_client=llm, workflow_service=workflow_service, tool_executor=tool_executor
    )

    app.dependency_overrides[get_agent_service] = lambda: agent_service
    try:
        chat_response = client.post(
            "/api/v1/chat", json={"message": "Find me a good restaurant nearby"}
        )
    finally:
        app.dependency_overrides.pop(get_agent_service, None)

    assert chat_response.status_code == 200
    workflow_id = chat_response.json()["workflow_id"]

    _override_workflow_service(workflow_session_factory)
    try:
        list_response = client.get("/api/v1/workflows")
        detail_response = client.get(f"/api/v1/workflows/{workflow_id}")
        steps_response = client.get(f"/api/v1/workflows/{workflow_id}/steps")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["workflow_id"] == workflow_id

    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "COMPLETED"
    assert detail_response.json()["final_response"] == "Here are some options."

    steps_body = steps_response.json()
    assert steps_body["total"] == 4
    assert [s["node_name"] for s in steps_body["items"]] == ["REASON", "PLAN", "ACT", "OBSERVE"]


def test_full_chat_approve_to_history_end_to_end_includes_approval_step(
    client, workflow_session_factory, db_session
):
    """End-to-end: an email request pauses, gets approved, and the history
    API shows the full REASON/PLAN/ACT/APPROVAL/ACT/OBSERVE trace."""
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
    workflow_id = chat_response.json()["workflow_id"]

    resume_llm = _QueuedLLMClient(["I've sent your email."])
    resume_agent_service = AgentService(
        llm_client=resume_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    app.dependency_overrides[get_agent_service] = lambda: resume_agent_service
    try:
        client.post(f"/api/v1/approvals/{workflow_id}/approve")
    finally:
        app.dependency_overrides.pop(get_agent_service, None)

    _override_workflow_service(workflow_session_factory)
    try:
        steps_response = client.get(f"/api/v1/workflows/{workflow_id}/steps")
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)

    body = steps_response.json()
    assert [s["node_name"] for s in body["items"]] == [
        "REASON",
        "PLAN",
        "ACT",
        "APPROVAL",
        "ACT",
        "OBSERVE",
    ]
    approval_step = body["items"][3]
    assert approval_step["tool_name"] == "email"
    assert "approved" in approval_step["action_summary"].lower()