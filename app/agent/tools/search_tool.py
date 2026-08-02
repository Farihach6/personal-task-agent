"""Mock Search Tool used during Milestone 6.

This is a fake search implementation. It returns realistic-looking
results without calling any external APIs.
"""

from typing import Any

from app.core.exceptions import GuardrailViolation
from app.core.logger import get_logger

logger = get_logger(__name__)


class SearchTool:
    """Mock search tool."""

    name = "search"

    def run(self, tool_input: dict[str, Any] | None) -> dict[str, Any]:
        """Return fake search results."""

        if tool_input is None:
            raise GuardrailViolation("Tool input cannot be None.")

        query = tool_input.get("query")

        if query is None or not isinstance(query, str) or not query.strip():
            raise GuardrailViolation("A non-empty query is required.")

        query = query.strip()

        logger.info("SearchTool executing query='%s'", query)

        return {
            "query": query,
            "results": [
                {
                    "title": f"Top result for '{query}'",
                    "snippet": f"Summary information about {query}.",
                    "url": f"https://example.com/search/1?q={query.replace(' ', '+')}",
                },
                {
                    "title": f"Second result for '{query}'",
                    "snippet": f"Additional information about {query}.",
                    "url": f"https://example.com/search/2?q={query.replace(' ', '+')}",
                },
                {
                    "title": f"Third result for '{query}'",
                    "snippet": f"More details related to {query}.",
                    "url": f"https://example.com/search/3?q={query.replace(' ', '+')}",
                },
            ],
        }