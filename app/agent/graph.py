"""LangGraph: Reason -> Plan pipeline.

Flow:
START -> reason_node -> plan_node -> END

Tool execution (Act/Observe) arrives in a later milestone.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.plan_node import build_plan_node
from app.agent.nodes.reason_node import build_reason_node
from app.agent.state import AgentState
from app.core.logger import get_logger
from app.llm.groq_client import GroqClient

logger = get_logger(__name__)


def build_graph(llm_client: GroqClient | None = None) -> CompiledStateGraph:
    """Build and compile the Reason → Plan graph."""

    client = llm_client or GroqClient()

    graph = StateGraph(AgentState)

    graph.add_node(
        "reason_node",
        build_reason_node(client),
    )

    graph.add_node(
        "plan_node",
        build_plan_node(client),
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
        END,
    )

    return graph.compile()