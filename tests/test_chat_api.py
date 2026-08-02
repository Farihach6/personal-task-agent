"""API-level tests for the /chat endpoint.

AgentService is overridden with a fake via FastAPI's dependency_overrides,
so most tests never invoke LangGraph, the real Groq API, or a real DB. One
test wires up the real agent stack (graph, tools, DB) against the isolated
in-memory test database for genuine end-to-end coverage.
"""

from app.agent.tools.notes_tool import NotesTool
from app.agent.tools.search_tool import SearchTool
from app.agent.tools.tool_executor import ToolExecutor
from app.database.repositories import NoteRepository
from app.main import app
from app.services.agent_service import AgentService, get_agent_service
from app.services.workflow_service import WorkflowService


class _FakeAgentService:
    def __init__(self, result: dict) -> None:
        self._result = result

    def run(self, user_input: str) -> dict:
        return self._result


class _QueuedLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def generate(self, prompt: str) -> str:
        return self._responses.pop(0)


def test_chat_endpoint_returns_intent_plan_and_final_response(client):
    fake_result = {
        "workflow_id": "wf-abc",
        "intent": "Book a flight",
        "plan": ["Search flights", "Confirm booking"],
        "final_response": "I've found some flight options for you to Paris.",
        "status": "COMPLETED",
    }
    app.dependency_overrides[get_agent_service] = lambda: _FakeAgentService(fake_result)
    try:
        response = client.post("/api/v1/chat", json={"message": "Book me a flight"})
    finally:
        app.dependency_overrides.pop(get_agent_service, None)

    assert response.status_code == 200
    assert response.json() == fake_result


def test_chat_endpoint_rejects_blank_message(client):
    response = client.post("/api/v1/chat", json={"message": "   "})
    assert response.status_code == 422


def test_chat_endpoint_rejects_missing_message(client):
    response = client.post("/api/v1/chat", json={})
    assert response.status_code == 422


def test_chat_endpoint_rejects_message_too_long(client):
    response = client.post("/api/v1/chat", json={"message": "x" * 4001})
    assert response.status_code == 422


def test_chat_endpoint_end_to_end_creates_note_via_notes_tool(
    client, workflow_session_factory, db_session
):
    """Full stack through the real HTTP endpoint: /chat -> AgentService ->
    graph -> Act -> ToolExecutor -> NotesTool -> NotesService -> Repository
    -> isolated test database -> Observe -> final_response. Only the LLM
    client is faked."""
    fake_llm = _QueuedLLMClient(["Save a note", '["Create the note"]', "I've saved your note."])
    workflow_service = WorkflowService(session_factory=workflow_session_factory)
    tool_executor = ToolExecutor(
        tools=[SearchTool(), NotesTool(session_factory=workflow_session_factory)]
    )
    real_agent_service = AgentService(
        llm_client=fake_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )

    app.dependency_overrides[get_agent_service] = lambda: real_agent_service
    try:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Save a note that tomorrow I have a dentist appointment"},
        )
    finally:
        app.dependency_overrides.pop(get_agent_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["final_response"] == "I've saved your note."

    notes = NoteRepository(db_session).list_all()
    assert len(notes) == 1
    assert "dentist" in notes[0].content.lower()