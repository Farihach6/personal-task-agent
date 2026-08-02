
"""API-level tests for the /chat endpoint.

AgentService is overridden with a fake via FastAPI dependency_overrides,
so these tests never invoke LangGraph, Groq API, tools, or a real database.
"""

from app.main import app
from app.services.agent_service import get_agent_service


class _FakeAgentService:
    def __init__(self, result: dict) -> None:
        self._result = result

    def run(self, user_input: str) -> dict:
        return self._result


def test_chat_endpoint_returns_full_agent_result(client):
    fake_result = {
        "workflow_id": "wf-abc",
        "intent": "Book a flight",
        "plan": [
            "Search flights",
            "Confirm booking",
        ],
        "final_response": (
            "I've found some flight options for you to Paris."
        ),
        "status": "COMPLETED",
    }

    app.dependency_overrides[get_agent_service] = (
        lambda: _FakeAgentService(fake_result)
    )

    try:
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Book me a flight"
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_agent_service,
            None,
        )

    assert response.status_code == 200
    assert response.json() == fake_result


def test_chat_endpoint_rejects_blank_message(client):

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "   "
        },
    )

    assert response.status_code == 422


def test_chat_endpoint_rejects_missing_message(client):

    response = client.post(
        "/api/v1/chat",
        json={}
    )

    assert response.status_code == 422


def test_chat_endpoint_rejects_message_too_long(client):

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "x" * 4001
        },
    )

    assert response.status_code == 422
