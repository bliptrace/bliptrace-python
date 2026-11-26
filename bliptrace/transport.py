"""Ships an envelope to the ingest API. Implementations must never throw."""

from __future__ import annotations

import json
import time
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from .retry import RetryPolicy


class Transport(ABC):
    """Transport contract. ``send`` must never raise into the host app."""

    @abstractmethod
    def send(
        self, endpoint: str, key: str, envelope: Dict[str, Any], timeout: float
    ) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class UrllibTransport(Transport):
    """Dependency-free transport using the stdlib ``urllib.request``.

    Retries on transient failures with exponential backoff + jitter. The same
    serialised body (hence the same ``event_id``) is replayed on every attempt, so
    the ingest API's idempotency dedupe makes this safe -- a retry never creates a
    duplicate occurrence (spec section 10).
    """

    def __init__(self, policy: Optional[RetryPolicy] = None) -> None:
        self.policy = policy or RetryPolicy()

    def send(
        self, endpoint: str, key: str, envelope: Dict[str, Any], timeout: float
    ) -> None:
        try:
            url = endpoint.rstrip("/") + "/v1/ingest"
            body = json.dumps(envelope).encode("utf-8")

            attempt = 0
            while True:
                status, retry_after = self._attempt(url, body, key, timeout)
                if not self.policy.should_retry(status, attempt):
                    return
                self._sleep_ms(self.policy.delay_ms(attempt, retry_after))
                attempt += 1
        except Exception:
            # Capturing must never break the monitored app.
            pass

    def _attempt(
        self, url: str, body: bytes, key: str, timeout: float
    ) -> Tuple[int, Optional[float]]:
        """Perform one HTTP attempt.

        Returns ``(status, retry_after_seconds)``; status is 0 on a transport
        error/timeout. Overridable so tests can script responses without a network.
        """
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Ingest-Key": key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=max(0.001, timeout)) as resp:
                return getattr(resp, "status", 200) or 200, self._parse_retry_after(
                    resp.headers.get("Retry-After")
                )
        except urllib.error.HTTPError as exc:  # server returned a >= 400 status
            retry_after = None
            headers = getattr(exc, "headers", None)
            if headers is not None:
                retry_after = self._parse_retry_after(headers.get("Retry-After"))
            return int(getattr(exc, "code", 0) or 0), retry_after
        except Exception:
            # Connection refused, DNS failure, timeout -- treat as a transport error.
            return 0, None

    @staticmethod
    def _parse_retry_after(value: Optional[str]) -> Optional[float]:
        """Parse a numeric ``Retry-After`` (seconds). Non-numeric values are ignored."""
        if value is None:
            return None
        try:
            return float(value.strip())
        except (TypeError, ValueError):
            return None

    def _sleep_ms(self, ms: int) -> None:
        """Sleep between attempts. Overridable so tests run without real delay."""
        if ms > 0:
            time.sleep(ms / 1000.0)
