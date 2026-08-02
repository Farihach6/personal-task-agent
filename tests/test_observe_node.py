"""Unit tests for the Observe node."""

from app.agent.nodes.observe_node import build_observe_node
from app.agent.state import create_initial_state


class _FakeLLMClient:
    def __init__(
        self,
        response: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.last_prompt: str | None = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt

        if self.error is not None:
            raise self.error

        return self.response


def test_observe_node_generates_final_response():
    fake_client = _FakeLLMClient(
        response="Here are some great restaurants nearby."
    )

    node = build_observe_node(fake_client)

    state = create_initial_state("wf-1", "Find restaurants")
    state["intent"] = "Find restaurants"
    state["plan"] = ["Search restaurants"]
    state["tool_result"] = {
        "query": "restaurants",
        "results": [],
    }

    result = node(state)

    assert result["final_response"] == "Here are some great restaurants nearby."
    assert result["status"] == "COMPLETED"
    assert result["current_step"] == "DONE"
    assert "observe_raw_response" in result["metadata"]


def test_observe_node_includes_context_in_prompt():
    fake_client = _FakeLLMClient(response="ok")

    node = build_observe_node(fake_client)

    state = create_initial_state("wf-2", "Find pizza")
    state["intent"] = "Find pizza places"
    state["plan"] = ["Search pizza places"]

    state["tool_result"] = {
        "query": "pizza",
        "results": [
            {
                "title": "Best Pizza",
            }
        ],
    }

    node(state)

    assert fake_client.last_prompt is not None
    assert "Find pizza" in fake_client.last_prompt
    assert "Find pizza places" in fake_client.last_prompt
    assert "Best Pizza" in fake_client.last_prompt


def test_observe_node_skips_llm_call_when_status_already_failed():
    fake_client = _FakeLLMClient(response="should not be used")

    node = build_observe_node(fake_client)

    state = create_initial_state("wf-3", "Find pizza")
    state["status"] = "FAILED"

    # Updated implementation stores failures under "error"
    state["metadata"]["error"] = "tool failed"

    result = node(state)

    assert fake_client.last_prompt is None
    assert result["status"] == "FAILED"
    assert result["final_response"]
    assert result["current_step"] == "DONE"


def test_observe_node_marks_failed_and_sets_fallback_on_llm_error():
    fake_client = _FakeLLMClient(
        error=RuntimeError("groq down")
    )

    node = build_observe_node(fake_client)

    state = create_initial_state("wf-4", "Find pizza")
    state["intent"] = "Find pizza"
    state["plan"] = ["Search pizza"]

    state["tool_result"] = {
        "query": "pizza",
        "results": [],
    }

    result = node(state)

    assert result["status"] == "FAILED"
    assert result["metadata"]["error"] == "groq down"
    assert result["final_response"] == (
        "I ran into an error while preparing a response."
    )
    assert result["current_step"] == "DONE"