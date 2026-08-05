"""LangGraph: Reason -> Plan -> Act -> Observe pipeline, with a conditional
pause after Act for tools that require human approval.

Flow:
    START -> reason_node -> plan_node -> act_node -> (approval needed?)
        no  -> observe_node -> END
        yes -> END (paused, awaiting approval)

Tool execution (Act) selects and runs the appropriate tool via
ToolExecutor; Observe turns the tool result into a natural-language
final_response. If Act pauses a sensitive tool (e.g. Email) for approval,
the conditional edge routes straight to END instead of Observe —
AgentService.resume() continues the pipeline later once a human decides.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.act_node import build_act_node
from app.agent.nodes.observe_node import build_observe_node
from app.agent.nodes.plan_node import build_plan_node
from app.agent.nodes.reason_node import build_reason_node
from app.agent.state import AgentState
from app.agent.tools.tool_executor import ToolExecutor
from app.core.logger import get_logger
from app.llm.groq_client import GroqClient

logger = get_logger(__name__)


def _route_after_act(state: AgentState) -> str:
    """Route to END if Act paused the workflow for approval; otherwise continue to Observe."""
    if state.get("status") == "WAITING_APPROVAL":
        return "paused"
    return "continue"


def build_graph(
    llm_client: GroqClient | None = None, tool_executor: ToolExecutor | None = None
) -> CompiledStateGraph:
    """Compile the Reason -> Plan -> Act -> Observe graph.

    Accepts an optional pre-built LLM client and tool executor so callers
    (and tests) can inject fakes instead of always constructing real ones.
    """
    client = llm_client or GroqClient()
    executor = tool_executor or ToolExecutor()

    graph = StateGraph(AgentState)
    graph.add_node("reason_node", build_reason_node(client))
    graph.add_node("plan_node", build_plan_node(client))
    graph.add_node("act_node", build_act_node(executor))
    graph.add_node("observe_node", build_observe_node(client))

    graph.add_edge(START, "reason_node")
    graph.add_edge("reason_node", "plan_node")
    graph.add_edge("plan_node", "act_node")
    graph.add_conditional_edges(
        "act_node",
        _route_after_act,
        {"paused": END, "continue": "observe_node"},
    )
    graph.add_edge("observe_node", END)

    return graph.compile()