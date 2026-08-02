"""Tool executor.

Dispatches a tool call to the appropriate tool implementation.
"""

from typing import Any, Protocol

from app.agent.tools.search_tool import SearchTool
from app.core.exceptions import GuardrailViolation, ToolExecutionError
from app.core.logger import get_logger

logger = get_logger(__name__)


class Tool(Protocol):
    """Interface every tool must implement."""

    name: str

    def run(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        ...


class ToolExecutor:
    """Registry + dispatcher for agent tools."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        registered = tools if tools is not None else [SearchTool()]
        self._tools: dict[str, Tool] = {
            tool.name: tool for tool in registered
        }

    def execute(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the requested tool."""

        tool = self._tools.get(tool_name)

        if tool is None:
            raise ToolExecutionError(f"Unknown tool: '{tool_name}'")

        try:
            return tool.run(tool_input)

        except GuardrailViolation:
            raise

        except ToolExecutionError:
            raise

        except Exception as exc:
            logger.exception("Tool '%s' failed", tool_name)
            raise ToolExecutionError(
                f"Tool '{tool_name}' failed: {exc}"
            ) from exc