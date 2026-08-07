"""Tests for AgentService. Both the LLM client and WorkflowService are fakes
here — no Groq SDK and no real database are ever touched, except in the
dedicated end-to-end test which uses the isolated in-memory test database."""

import pytest

from app.agent.tools.email_tool import EmailTool
from app.agent.tools.notes_tool import NotesTool
from app.agent.tools.search_tool import SearchTool
from app.agent.tools.tool_executor import ToolExecutor
from app.core.exceptions import GuardrailViolation, ToolExecutionError
from app.database.repositories import NoteRepository, WorkflowStepRepository
from app.services.agent_service import AgentService
from app.services.workflow_service import WorkflowService


class _FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def generate(self, prompt: str) -> str:
        return self._responses.pop(0)


class _FailingToolExecutor:
    def execute(self, tool_name: str, tool_input: dict) -> dict:
        raise ToolExecutionError("search backend down")


class _FakeWorkflowService:
    """Records calls in-memory instead of touching a real database."""

    def __init__(self) -> None:
        self.created_prompts: list[str] = []
        self.recorded_steps: list[dict] = []
        self.finalized: list[dict] = []
        self.awaiting_approval: list[str] = []
        self._next_id = 1

    def create_workflow(self, user_prompt: str) -> str:
        self.created_prompts.append(user_prompt)
        workflow_id = f"fake-wf-{self._next_id}"
        self._next_id += 1
        return workflow_id

    def record_step(self, workflow_id, node_type, input_data, output_data, tool_name=None) -> None:
        self.recorded_steps.append(
            {
                "workflow_id": workflow_id,
                "node_type": node_type,
                "input_data": input_data,
                "output_data": output_data,
                "tool_name": tool_name,
            }
        )

    def save_step(
        self, workflow_id, node_name, action_summary, tool_name=None, tool_input=None, tool_output=None
    ) -> None:
        self.recorded_steps.append(
            {
                "workflow_id": workflow_id,
                "node_type": node_name.upper(),
                "input_data": {"tool_name": tool_name, "tool_input": tool_input},
                "output_data": {"action_summary": action_summary, "tool_output": tool_output},
                "tool_name": tool_name,
            }
        )

    def finalize_workflow(
        self, workflow_id, status, final_response=None, tools_used=None, approval_status=None
    ) -> None:
        self.finalized.append(
            {
                "workflow_id": workflow_id,
                "status": status,
                "final_response": final_response,
                "approval_status": approval_status,
            }
        )

    def mark_awaiting_approval(self, workflow_id: str) -> None:
        self.awaiting_approval.append(workflow_id)

    def get_pending_approvals(self) -> list[dict]:
        return [{"workflow_id": wf_id} for wf_id in self.awaiting_approval]

    def get_workflow_context(self, workflow_id: str) -> dict:
        return getattr(self, "_context", {})


def test_agent_service_run_returns_full_result_with_final_response():
    llm = _FakeLLMClient(
        ["Book a flight", '["Search flights", "Confirm booking"]', "Here's your flight info."]
    )
    workflow_service = _FakeWorkflowService()
    service = AgentService(llm_client=llm, workflow_service=workflow_service)

    result = service.run("Book me a flight to Paris")

    assert result["intent"] == "Book a flight"
    assert result["plan"] == ["Search flights", "Confirm booking"]
    assert result["final_response"] == "Here's your flight info."
    assert result["status"] == "COMPLETED"
    assert result["workflow_id"] == "fake-wf-1"


def test_agent_service_run_creates_workflow_with_user_message():
    llm = _FakeLLMClient(["intent", "[]", "ok"])
    workflow_service = _FakeWorkflowService()
    service = AgentService(llm_client=llm, workflow_service=workflow_service)

    service.run("Order me dinner")

    assert workflow_service.created_prompts == ["Order me dinner"]


def test_agent_service_run_records_a_step_per_node():
    llm = _FakeLLMClient(["intent", '["step one"]', "final answer"])
    workflow_service = _FakeWorkflowService()
    service = AgentService(llm_client=llm, workflow_service=workflow_service)

    service.run("Hello")

    node_types = [step["node_type"] for step in workflow_service.recorded_steps]
    assert node_types == ["REASON", "PLAN", "ACT", "OBSERVE"]


def test_agent_service_run_finalizes_workflow_with_final_response():
    llm = _FakeLLMClient(["intent", "[]", "Here's the answer."])
    workflow_service = _FakeWorkflowService()
    service = AgentService(llm_client=llm, workflow_service=workflow_service)

    result = service.run("Hello")

    assert workflow_service.finalized == [
        {
            "workflow_id": result["workflow_id"],
            "status": "COMPLETED",
            "final_response": "Here's the answer.",
            "approval_status": None,
        }
    ]


def test_agent_service_run_finalizes_as_failed_when_tool_fails():
    # Reason and plan still run; observe skips its LLM call once status is
    # FAILED, so only 2 responses are consumed.
    llm = _FakeLLMClient(["intent", "[]"])
    workflow_service = _FakeWorkflowService()
    service = AgentService(
        llm_client=llm, workflow_service=workflow_service, tool_executor=_FailingToolExecutor()
    )

    result = service.run("Hello")

    assert result["status"] == "FAILED"
    assert result["final_response"]  # fallback response still present
    assert workflow_service.finalized[0]["status"] == "FAILED"


def test_agent_service_run_finalizes_as_failed_and_reraises_on_unexpected_error():
    class _BoomLLMClient:
        def generate(self, prompt: str) -> str:
            raise RuntimeError("boom")

    workflow_service = _FakeWorkflowService()
    service = AgentService(llm_client=_BoomLLMClient(), workflow_service=workflow_service)

    with pytest.raises(RuntimeError):
        service.run("Hello")

    assert workflow_service.finalized[0]["workflow_id"] == "fake-wf-1"
    assert workflow_service.finalized[0]["status"] == "FAILED"


def test_agent_service_run_creates_a_real_note_end_to_end(workflow_session_factory, db_session):
    """Full stack, real components: AgentService -> graph -> Act -> ToolExecutor
    -> NotesTool -> NotesService -> Repository -> isolated test database.
    Only the LLM client is faked."""
    llm = _FakeLLMClient(["Save a note", '["Create the note"]', "I've saved your note."])
    workflow_service = WorkflowService(session_factory=workflow_session_factory)
    tool_executor = ToolExecutor(
        tools=[SearchTool(), NotesTool(session_factory=workflow_session_factory)]
    )
    service = AgentService(llm_client=llm, workflow_service=workflow_service, tool_executor=tool_executor)

    result = service.run("Save a note that I need to call the plumber")

    assert result["status"] == "COMPLETED"
    assert result["final_response"] == "I've saved your note."

    notes = NoteRepository(db_session).list_all()
    assert len(notes) == 1
    assert "plumber" in notes[0].content.lower()

    steps = WorkflowStepRepository(db_session).get_by_workflow(result["workflow_id"])
    assert [s.node_type for s in steps] == ["REASON", "PLAN", "ACT", "OBSERVE"]


def test_agent_service_run_still_uses_search_end_to_end_for_non_note_requests(
    workflow_session_factory, db_session
):
    """Regression check: with NotesTool registered, ordinary requests still
    route through SearchTool and never touch the notes table."""
    llm = _FakeLLMClient(["Find restaurants", '["Search restaurants"]', "Here are some options."])
    workflow_service = WorkflowService(session_factory=workflow_session_factory)
    tool_executor = ToolExecutor(
        tools=[SearchTool(), NotesTool(session_factory=workflow_session_factory)]
    )
    service = AgentService(llm_client=llm, workflow_service=workflow_service, tool_executor=tool_executor)

    result = service.run("Find me a good restaurant")

    assert result["status"] == "COMPLETED"
    assert NoteRepository(db_session).count() == 0


class _RequiresApprovalToolExecutor:
    def execute(self, tool_name: str, tool_input: dict) -> dict:
        raise AssertionError("Tool must not execute before approval is granted")

    def requires_approval(self, tool_name: str) -> bool:
        return True


def test_agent_service_run_pauses_workflow_when_tool_requires_approval():
    llm = _FakeLLMClient(["Send an email", '["Send the email"]'])
    workflow_service = _FakeWorkflowService()
    service = AgentService(
        llm_client=llm,
        workflow_service=workflow_service,
        tool_executor=_RequiresApprovalToolExecutor(),
    )

    result = service.run("Send an email to john@example.com saying hi")

    assert result["status"] == "WAITING_APPROVAL"
    assert result["workflow_id"] in workflow_service.awaiting_approval
    assert workflow_service.finalized == []  # a paused workflow is not finalized


class _FakeEmailService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send_email(self, to: str, subject: str, body: str) -> dict:
        self.calls.append({"to": to, "subject": subject, "body": body})
        return {"sent": True, "simulated": False, "to": to, "subject": subject,"body": body}


def test_agent_service_resume_approves_and_sends_the_email(workflow_session_factory, db_session):
    """Full pause -> approve -> execute -> observe -> finalize lifecycle
    against the isolated test database. Only the LLM client is faked."""
    workflow_service = WorkflowService(session_factory=workflow_session_factory)
    fake_email_service = _FakeEmailService()
    tool_executor = ToolExecutor(
        tools=[SearchTool(), EmailTool(email_service=fake_email_service)]
    )

    pause_llm = _FakeLLMClient(["Send an email", '["Send the email"]'])
    service = AgentService(
        llm_client=pause_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    paused = service.run("Send an email to john@example.com saying the meeting is at 3pm")
    assert paused["status"] == "WAITING_APPROVAL"

    resume_llm = _FakeLLMClient(["I've sent your email."])
    resume_service = AgentService(
        llm_client=resume_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    result = resume_service.resume(paused["workflow_id"], approved=True)

    assert result["status"] == "COMPLETED"
    assert result["final_response"] == "I've sent your email."
    assert fake_email_service.calls == [
        {"to": "john@example.com", "subject": "Send an email", "body": "the meeting is at 3pm"}
    ]

    steps = WorkflowStepRepository(db_session).get_by_workflow(paused["workflow_id"])
    assert [s.node_type for s in steps] == ["REASON", "PLAN", "ACT", "APPROVAL", "ACT", "OBSERVE"]


def test_agent_service_resume_rejects_and_never_sends_the_email(workflow_session_factory, db_session):
    workflow_service = WorkflowService(session_factory=workflow_session_factory)
    fake_email_service = _FakeEmailService()
    tool_executor = ToolExecutor(
        tools=[SearchTool(), EmailTool(email_service=fake_email_service)]
    )

    pause_llm = _FakeLLMClient(["Send an email", '["Send the email"]'])
    service = AgentService(
        llm_client=pause_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    paused = service.run("Send an email to jane@example.com saying hello")
    assert paused["status"] == "WAITING_APPROVAL"

    reject_llm = _FakeLLMClient(["Okay, I won't send that email."])
    resume_service = AgentService(
        llm_client=reject_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    result = resume_service.resume(paused["workflow_id"], approved=False)

    assert result["status"] == "COMPLETED"
    assert result["final_response"] == "Okay, I won't send that email."
    assert fake_email_service.calls == []  # never actually sent

    from app.database.repositories import WorkflowRepository

    workflow = WorkflowRepository(db_session).get_by_id(paused["workflow_id"])
    assert workflow.approval_status == "REJECTED"


def test_agent_service_pending_approvals_list_clears_after_resume(
    workflow_session_factory, db_session
):
    workflow_service = WorkflowService(session_factory=workflow_session_factory)
    tool_executor = ToolExecutor(
        tools=[SearchTool(), EmailTool(email_service=_FakeEmailService())]
    )

    llm = _FakeLLMClient(["Send an email", '["Send the email"]'])
    service = AgentService(llm_client=llm, workflow_service=workflow_service, tool_executor=tool_executor)
    paused = service.run("Send an email to john@example.com saying hi")

    assert len(workflow_service.get_pending_approvals()) == 1

    resume_llm = _FakeLLMClient(["Sent."])
    resume_service = AgentService(
        llm_client=resume_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    resume_service.resume(paused["workflow_id"], approved=True)

    assert workflow_service.get_pending_approvals() == []


def test_agent_service_resume_is_idempotent_and_does_not_resend_on_second_approval(
    workflow_session_factory, db_session
):
    """Regression: calling resume() twice on the same workflow must not
    execute the sensitive tool (e.g. send the email) a second time."""
    workflow_service = WorkflowService(session_factory=workflow_session_factory)
    fake_email_service = _FakeEmailService()
    tool_executor = ToolExecutor(
        tools=[SearchTool(), EmailTool(email_service=fake_email_service)]
    )

    pause_llm = _FakeLLMClient(["Send an email", '["Send the email"]'])
    service = AgentService(
        llm_client=pause_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    paused = service.run("Send an email to john@example.com saying hi")

    first_llm = _FakeLLMClient(["Sent once."])
    first_resume_service = AgentService(
        llm_client=first_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    first_result = first_resume_service.resume(paused["workflow_id"], approved=True)
    assert first_result["status"] == "COMPLETED"
    assert len(fake_email_service.calls) == 1

    second_llm = _FakeLLMClient(["Sent again?!"])
    second_resume_service = AgentService(
        llm_client=second_llm, workflow_service=workflow_service, tool_executor=tool_executor
    )
    with pytest.raises(GuardrailViolation):
        second_resume_service.resume(paused["workflow_id"], approved=True)

    # The email must still only have been sent once.
    assert len(fake_email_service.calls) == 1


def test_agent_service_resume_rejects_when_workflow_is_not_awaiting_approval(
    workflow_session_factory, db_session
):
    """Regression: resume() must refuse to act on a workflow that was never
    paused (e.g. a normal already-COMPLETED search workflow)."""
    workflow_service = WorkflowService(session_factory=workflow_session_factory)
    tool_executor = ToolExecutor(tools=[SearchTool()])

    llm = _FakeLLMClient(["Find restaurants", '["Search restaurants"]', "Here are some options."])
    service = AgentService(llm_client=llm, workflow_service=workflow_service, tool_executor=tool_executor)
    result = service.run("Find me a good restaurant")
    assert result["status"] == "COMPLETED"

    with pytest.raises(GuardrailViolation):
        service.resume(result["workflow_id"], approved=True)