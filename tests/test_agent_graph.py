"""Tests for the Reason -> Plan -> Act -> Observe LangGraph graph."""

from app.agent.graph import build_graph
from app.agent.state import create_initial_state
from app.agent.tools.notes_tool import NotesTool
from app.agent.tools.search_tool import SearchTool
from app.agent.tools.tool_executor import ToolExecutor
from app.core.exceptions import ToolExecutionError
from app.database.repositories import NoteRepository


class _FakeLLMClient:
    """Stand-in for GroqClient so graph tests never touch the real SDK.

    Returns a queued sequence of responses, one per call, so reason/plan/
    observe can each get a distinct canned response (act does not call the LLM).
    """

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._responses.pop(0)


class _FailingToolExecutor:
    def execute(self, tool_name: str, tool_input: dict) -> dict:
        raise ToolExecutionError("search backend down")


def test_graph_executes_all_four_nodes_and_produces_final_response():
    fake_client = _FakeLLMClient(
        responses=[
            "Find restaurants",
            '["Search restaurants", "Pick best one"]',
            "Here are some great restaurant options nearby.",
        ]
    )
    graph = build_graph(fake_client)

    final_state = graph.invoke(create_initial_state("wf-1", "Find me a good restaurant"))

    assert final_state["intent"] == "Find restaurants"
    assert final_state["plan"] == ["Search restaurants", "Pick best one"]
    assert final_state["tool_name"] == "search"
    assert final_state["tool_result"]["query"] == "Find restaurants"
    assert final_state["final_response"] == "Here are some great restaurant options nearby."
    assert final_state["status"] == "COMPLETED"
    assert final_state["current_step"] == "DONE"


def test_graph_calls_reason_plan_observe_in_order_with_correct_prompts():
    fake_client = _FakeLLMClient(
        responses=["Order food", '["Pick a restaurant", "Place order"]', "Your order is on its way!"]
    )
    graph = build_graph(fake_client)

    graph.invoke(create_initial_state("wf-2", "I'm hungry, order me dinner"))

    assert len(fake_client.calls) == 3
    assert "I'm hungry, order me dinner" in fake_client.calls[0]
    assert "Order food" in fake_client.calls[1]  # plan prompt includes reason's intent
    assert "Order food" in fake_client.calls[2]  # observe prompt includes intent too


def test_graph_falls_back_to_single_step_plan_on_malformed_json():
    fake_client = _FakeLLMClient(responses=["Do something", "not valid json at all", "Done."])
    graph = build_graph(fake_client)

    final_state = graph.invoke(create_initial_state("wf-3", "Do the thing"))

    assert final_state["plan"] == ["Respond to: Do the thing"]
    assert final_state["status"] == "COMPLETED"


def test_graph_preserves_workflow_id():
    fake_client = _FakeLLMClient(responses=["intent", "[]", "ok"])
    graph = build_graph(fake_client)

    final_state = graph.invoke(create_initial_state("wf-preserved", "Hello"))

    assert final_state["workflow_id"] == "wf-preserved"


def test_graph_marks_failed_and_still_produces_final_response_when_tool_fails():
    # Only reason and plan call the LLM; observe skips its LLM call once
    # status is already FAILED, so only 2 responses are ever consumed.
    fake_client = _FakeLLMClient(responses=["intent", "[]"])
    graph = build_graph(fake_client, tool_executor=_FailingToolExecutor())

    final_state = graph.invoke(create_initial_state("wf-4", "Hello"))

    assert final_state["status"] == "FAILED"
    assert "error" in final_state["metadata"]
    assert final_state["final_response"]  # a fallback message is still produced
    assert final_state["current_step"] == "DONE"


def test_graph_executes_notes_create_action_end_to_end(workflow_session_factory, db_session):
    """Full Reason -> Plan -> Act -> Observe run against the real NotesTool,
    bound to the isolated in-memory test database (no real DB file touched)."""
    fake_client = _FakeLLMClient(
        responses=["Save a note", '["Create the note"]', "I've saved your note."]
    )
    tool_executor = ToolExecutor(
        tools=[SearchTool(), NotesTool(session_factory=workflow_session_factory)]
    )
    graph = build_graph(fake_client, tool_executor=tool_executor)

    final_state = graph.invoke(
        create_initial_state("wf-notes-1", "Save a note that tomorrow I have a dentist appointment")
    )

    assert final_state["tool_name"] == "notes"
    assert final_state["tool_result"]["observation"] == "note_created"
    assert final_state["final_response"] == "I've saved your note."
    assert final_state["status"] == "COMPLETED"

    notes = NoteRepository(db_session).list_all()
    assert len(notes) == 1
    assert "dentist" in notes[0].content.lower()


def test_graph_still_routes_to_search_when_notes_tool_is_registered():
    """Regression check: registering NotesTool must not change routing for
    ordinary (non-note) requests."""
    fake_client = _FakeLLMClient(
        responses=["Find restaurants", '["Search restaurants"]', "Here are some options."]
    )
    tool_executor = ToolExecutor(tools=[SearchTool(), NotesTool()])
    graph = build_graph(fake_client, tool_executor=tool_executor)

    final_state = graph.invoke(create_initial_state("wf-regression", "Find me a good restaurant"))

    assert final_state["tool_name"] == "search"
    assert final_state["status"] == "COMPLETED"