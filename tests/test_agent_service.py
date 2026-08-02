
"""Tests for AgentService 4-node graph.

Covers:
- REASON node
- PLAN node
- ACT node
- OBSERVE node
- final_response handling
- tool failure path
- unexpected errors

No real Groq API or database is used.
"""

import pytest

from app.core.exceptions import ToolExecutionError
from app.services.agent_service import AgentService


class _FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def generate(self, prompt: str) -> str:
        return self._responses.pop(0)


class _FailingToolExecutor:
    def execute(self, tool_name: str, tool_input: dict) -> dict:
        raise ToolExecutionError("search backend down")


class _FakeWorkflowService:
    def __init__(self) -> None:
        self.created_prompts = []
        self.recorded_steps = []
        self.finalized = []
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
    ):
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
    ):
        self.finalized.append(
            {
                "workflow_id": workflow_id,
                "status": status,
                "final_response": final_response,
            }
        )


def test_agent_service_returns_final_response():
    llm = _FakeLLMClient(
        [
            "Book a flight",
            '["Search flights", "Confirm booking"]',
            "Your flight information is ready.",
        ]
    )

    workflow_service = _FakeWorkflowService()

    service = AgentService(
        llm_client=llm,
        workflow_service=workflow_service,
    )

    result = service.run("Book me a flight to Paris")

    assert result["intent"] == "Book a flight"

    assert result["plan"] == [
        "Search flights",
        "Confirm booking",
    ]

    assert result["final_response"] == (
        "Your flight information is ready."
    )

    assert result["status"] == "COMPLETED"


def test_agent_service_creates_workflow_with_user_prompt():
    llm = _FakeLLMClient(
        [
            "intent",
            "[]",
            "final",
        ]
    )

    workflow_service = _FakeWorkflowService()

    service = AgentService(
        llm_client=llm,
        workflow_service=workflow_service,
    )

    service.run("Order dinner")

    assert workflow_service.created_prompts == [
        "Order dinner"
    ]


def test_agent_service_records_all_four_nodes():

    llm = _FakeLLMClient(
        [
            "intent",
            '["step one"]',
            "final answer",
        ]
    )

    workflow_service = _FakeWorkflowService()

    service = AgentService(
        llm_client=llm,
        workflow_service=workflow_service,
    )

    service.run("Hello")

    node_types = [
        step["node_type"]
        for step in workflow_service.recorded_steps
    ]

    assert node_types == [
        "REASON",
        "PLAN",
        "ACT",
        "OBSERVE",
    ]


def test_agent_service_finalizes_completed_with_response():

    llm = _FakeLLMClient(
        [
            "intent",
            "[]",
            "Completed successfully",
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
            "final_response": "Completed successfully",
        }
    ]


def test_agent_service_handles_tool_failure():

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
        tool_executor=_FailingToolExecutor(),
    )

    result = service.run("Search something")

    assert result["status"] == "FAILED"

    assert result["final_response"]

    assert workflow_service.finalized[0]["status"] == "FAILED"


def test_agent_service_finalizes_failed_on_unexpected_exception():

    class _BoomLLMClient:
        def generate(self, prompt: str):
            raise RuntimeError("boom")


    workflow_service = _FakeWorkflowService()

    service = AgentService(
        llm_client=_BoomLLMClient(),
        workflow_service=workflow_service,
    )

    with pytest.raises(RuntimeError):
        service.run("Hello")


    assert workflow_service.finalized[0] == {
        "workflow_id": "fake-wf-1",
        "status": "FAILED",
        "final_response": None,
    }
