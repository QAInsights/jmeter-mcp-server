"""
JSON formatting helpers for MCP tool output.

Tools support format="markdown" (default, unchanged human-readable text)
or format="json" (machine-readable {"ok": ..., "data"/"error"} envelope).
"""

import dataclasses
import enum
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (set, frozenset, tuple)):
        return list(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def to_json(data: Any, indent: int = 2) -> str:
    """Serialize data to JSON, handling datetime/Path/Enum/set/dataclass."""
    return json.dumps(data, default=_json_default, ensure_ascii=False, indent=indent)


def json_ok(data: Any) -> str:
    """Success envelope."""
    return to_json({"ok": True, "data": data})


def json_error(message: str, **extra) -> str:
    """Error envelope."""
    return to_json({"ok": False, "error": message, **extra})


def normalize_format(fmt: Optional[str]) -> str:
    """Normalize a format argument to 'json' or 'markdown'."""
    if fmt is None:
        return "markdown"
    value = str(fmt).strip().lower()
    if value == "md":
        value = "markdown"
    if value not in ("json", "markdown"):
        raise ValueError("format must be 'json' or 'markdown'")
    return value
