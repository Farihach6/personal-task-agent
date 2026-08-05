"""Tool executor.

Dispatches a tool call by name to the appropriate tool implementation. New
tools (Search, Notes, Email, ...) register here without changing the Act
node or graph structure. The registry pattern keeps tool selection
decoupled from tool execution.
"""

from typing import Any, Protocol

from app.agent.tools.email_tool import EmailTool
from app.agent.tools.notes_tool import NotesTool
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
        registered = (
            tools
            if tools is not None
            else [
                SearchTool(),
                NotesTool(),
                EmailTool(),
            ]
        )

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

        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool '%s' failed.", tool_name)

            raise ToolExecutionError(
                f"Tool '{tool_name}' failed: {exc}"
            ) from exc

    def requires_approval(self, tool_name: str) -> bool:
        """Return whether the tool requires human approval."""

        tool = self._tools.get(tool_name)

        if tool is None:
            raise ToolExecutionError(f"Unknown tool: '{tool_name}'")

        return bool(getattr(tool, "requires_approval", False))