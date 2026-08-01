"""Utility functions for JSON serialization and deserialization.

Used for SQLite TEXT columns that store JSON data such as:
- Workflow.tools_used
- WorkflowStep.input_data
- WorkflowStep.output_data
"""

from __future__ import annotations

import json
from typing import Any


def to_json(data: Any) -> str:
    """Convert a Python object into a JSON string."""

    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Failed to serialize data to JSON: {exc}") from exc


def from_json(raw: str | None, default: Any = None) -> Any:
    """Convert a JSON string back into a Python object.

    Returns the provided default value if the input is None or invalid JSON.
    """

    if raw is None:
        return default

    if isinstance(raw, str):
        raw = raw.strip()

    if not raw:
        return default

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default