"""Tests for AgentService.

Both the LLM client and WorkflowService are fakes, so no real Groq API,
LangGraph side effects, or database are touched.
"""

import pytest

from app.services.agent_service import AgentService


class _FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def generate(self, prompt: str) -> str:
        return self._responses.pop(0)


class _BoomLLMClient:
    def generate(self, prompt: str) -> str:
        raise RuntimeError("boom")


class _FakeWorkflowService:
    """In-memory fake implementation of WorkflowService."""

    def __init__(self) -> None:
        self.created_prompts: list[str] = []
        self.recorded_steps: list[dict] = []
        self.finalized: list[dict] = []
        self._next_id = 1

    def create_workflow(self, user_prompt: str) -> str:
        self.created_prompts.append(user_prompt)

        workflow_id = f"fake-wf-{self._next_id}"
        self._next_id += 1

        return workflow_id

    def record_step(
        self,
        workflow_id,
        node_type,
        input_data,
        output_data,
    ) -> None:
        self.recorded_steps.append(
            {
                "workflow_id": workflow_id,
                "node_type": node_type,
                "input_data": input_data,
                "output_data": output_data,
            }
        )

    def finalize_workflow(
        self,
        workflow_id,
        status,
        final_response=None,
        tools_used=None,
    ) -> None:
        self.finalized.append(
            {
                "workflow_id": workflow_id,
                "status": status,
            }
        )


def test_agent_service_run_returns_intent_and_plan():
    llm = _FakeLLMClient(
        [
            "Book a flight",
            '["Search flights", "Confirm booking"]',
        ]
    )

    workflow_service = _FakeWorkflowService()

    service = AgentService(
        llm_client=llm,
        workflow_service=workflow_service,
    )

    result = service.run("Book me a flight to Paris")

    assert result["workflow_id"] == "fake-wf-1"
    assert result["intent"] == "Book a flight"
    assert result["plan"] == [
        "Search flights",
        "Confirm booking",
    ]
    assert result["status"] == "COMPLETED"


def test_agent_service_creates_workflow():
    llm = _FakeLLMClient(["intent", "[]"])

    workflow_service = _FakeWorkflowService()

    service = AgentService(
        llm_client=llm,
        workflow_service=workflow_service,
    )

    service.run("Order dinner")

    assert workflow_service.created_prompts == [
        "Order dinner"
    ]


def test_agent_service_records_reason_and_plan_steps():
    llm = _FakeLLMClient(
        [
            "intent",
            '["step one"]',
        ]
    )

    workflow_service = _FakeWorkflowService()

    service = AgentService(
        llm_client=llm,
        workflow_service=workflow_service,
    )

    service.run("Hello")

    assert len(workflow_service.recorded_steps) == 2

    assert workflow_service.recorded_steps[0]["node_type"] == "REASON"
    assert workflow_service.recorded_steps[1]["node_type"] == "PLAN"


def test_agent_service_finalizes_completed_workflow():
    llm = _FakeLLMClient(
        [
            "intent",
            "[]",
        ]
    )

    workflow_service = _FakeWorkflowService()

    service = AgentService(
        llm_client=llm,
        workflow_service=workflow_service,
    )

    result = service.run("Hello")

    assert workflow_service.finalized == [
        {
            "workflow_id": result["workflow_id"],
            "status": "COMPLETED",
        }
    ]


def test_agent_service_finalizes_failed_workflow():
    workflow_service = _FakeWorkflowService()

    service = AgentService(
        llm_client=_BoomLLMClient(),
        workflow_service=workflow_service,
    )

    with pytest.raises(RuntimeError):
        service.run("Hello")

    assert workflow_service.finalized == [
        {
            "workflow_id": "fake-wf-1",
            "status": "FAILED",
        }
    ]