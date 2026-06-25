"""Client-side PII scrub: redact sensitive keys before sending."""

from __future__ import annotations

from typing import Any, List, Sequence


class Scrubber:
    """Recursively redacts configured keys (case-insensitive) in a context dict."""

    def __init__(self, keys: Sequence[str] = ()) -> None:
        self._keys: List[str] = [str(k).lower() for k in (keys or [])]

    def scrub(self, data: Any) -> Any:
        return self._walk(data)

    def _walk(self, value: Any) -> Any:
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                if isinstance(k, str) and k.lower() in self._keys:
                    out[k] = "[REDACTED]"
                else:
                    out[k] = self._walk(v)
            return out
        if isinstance(value, (list, tuple)):
            return [self._walk(v) for v in value]
        return value
