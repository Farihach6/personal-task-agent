"""LangGraph: Reason -> Plan -> Act -> Observe pipeline.

Flow:
START -> reason_node -> plan_node -> act_node -> observe_node -> END

The Act node executes a tool through ToolExecutor.
The Observe node turns the tool result into the final response.
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


def build_graph(
    llm_client: GroqClient | None = None,
    tool_executor: ToolExecutor | None = None,
) -> CompiledStateGraph:
    """Build and compile the Reason → Plan → Act → Observe graph."""

    client = llm_client or GroqClient()
    executor = tool_executor or ToolExecutor()

    graph = StateGraph(AgentState)

    graph.add_node(
        "reason_node",
        build_reason_node(client),
    )

    graph.add_node(
        "plan_node",
        build_plan_node(client),
    )

    graph.add_node(
        "act_node",
        build_act_node(executor),
    )

    graph.add_node(
        "observe_node",
        build_observe_node(client),
    )

    graph.add_edge(
        START,
        "reason_node",
    )

    graph.add_edge(
        "reason_node",
        "plan_node",
    )

    graph.add_edge(
        "plan_node",
        "act_node",
    )

    graph.add_edge(
        "act_node",
        "observe_node",
    )

    graph.add_edge(
        "observe_node",
        END,
    )

    logger.info("Reason → Plan → Act → Observe graph compiled successfully.")

    return graph.compile()