"""Builds the language-neutral g8scope error envelope from a Python exception."""

from __future__ import annotations

import platform
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import Config


def build_envelope(
    exc: BaseException, config: Config, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build the error envelope. ``context`` is assumed already scrubbed."""
    return {
        "schema_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "occurred_at": _now(),
        "runtime": {"name": "python", "version": platform.python_version()},
        "sdk": {"name": config.sdk_name, "version": config.sdk_version},
        "environment": config.environment,
        "release": config.release,
        "level": _level(exc),
        "exception": {
            "type": type(exc).__name__,
            "message": _limit(str(exc), config.max_message),
            "frames": _frames(exc, config),
        },
        "context": _normalise_context(context or {}),
    }


def _now() -> str:
    """RFC3339 UTC with millisecond precision, e.g. 2026-06-25T09:14:32.521Z."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _level(exc: BaseException) -> str:
    if isinstance(exc, (SystemExit, KeyboardInterrupt)):
        return "fatal"
    return "error"


def _frames(exc: BaseException, config: Config) -> List[Dict[str, Any]]:
    tb = exc.__traceback__
    extracted = traceback.extract_tb(tb)
    frames: List[Dict[str, Any]] = []
    for fs in extracted:
        frames.append(
            {
                "file": fs.filename,
                "line": fs.lineno or 0,
                "function": fs.name,
                "in_app": _in_app(fs.filename, config.base_path),
            }
        )
    return frames[: config.max_frames]


def _in_app(file: Optional[str], base_path: str) -> bool:
    if not file:
        return False
    if "site-packages" in file or "dist-packages" in file:
        return False
    return base_path != "" and file.startswith(base_path)


def _limit(value: str, max_len: int) -> str:
    return value[:max_len] if len(value) > max_len else value


def _normalise_context(context: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(context)
    custom = out.get("custom")
    if not custom:
        out["custom"] = {}
    return out
