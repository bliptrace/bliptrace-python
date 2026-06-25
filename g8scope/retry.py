"""Decides whether a failed ingest attempt should be retried, and how long to wait.

The SDK owns "the backend might be briefly down or shedding load (429)". Strategy
mirrors the PHP/JS SDKs: exponential backoff (base x 2**attempt), +/-25% jitter to
avoid a synchronised thundering herd, and a hard cap on both attempts and delay so
capturing can never block the monitored app for long. Retries are only safe because
the envelope's ``event_id`` is reused across attempts and the ingest API dedupes on
it (spec section 10).

Pure and immutable: no I/O, no sleeping -- that lives in the transport.
"""

from __future__ import annotations

import random
from typing import Callable, Optional

from .config import Config


class RetryPolicy:
    """Pure, unit-testable backoff policy. Holds no state between calls."""

    def __init__(
        self,
        max_retries: int = 2,
        base_ms: int = 100,
        cap_ms: int = 2000,
    ) -> None:
        self.max_retries = int(max_retries)
        self.base_ms = int(base_ms)
        self.cap_ms = int(cap_ms)

    @classmethod
    def from_config(cls, config: Config) -> "RetryPolicy":
        """Build from the SDK config (framework adapters pass their own values)."""
        return cls(config.max_retries, config.retry_base_ms, config.retry_cap_ms)

    def should_retry(self, status: int, attempt: int) -> bool:
        """Retry after seeing ``status``, having already done ``attempt`` retries?

        Retry only while ``attempt < max_retries`` and the status is retryable.
        """
        if attempt >= self.max_retries:
            return False
        return self.is_retryable(status)

    def is_retryable(self, status: int) -> bool:
        """Retryable: transport errors/timeouts (0), 408, 429, and any 5xx.

        Never retry a 2xx (success) or other 4xx (the request itself is bad).
        """
        return status == 0 or status == 408 or status == 429 or status >= 500

    def delay_ms(
        self,
        attempt: int,
        retry_after_seconds: Optional[float] = None,
        jitter: Optional[Callable[[], float]] = None,
    ) -> int:
        """Delay before the next attempt, in milliseconds.

        A server-sent ``Retry-After`` (seconds) wins, capped to ``cap_ms`` so a hostile
        or misconfigured header can't stall the app. Otherwise: exponential backoff with
        +/-25% jitter, capped at ``cap_ms``. ``jitter`` returns a float in [0,1) and is
        injectable for deterministic tests; it defaults to a uniform random draw.
        """
        if retry_after_seconds is not None and retry_after_seconds > 0:
            return min(self.cap_ms, int(retry_after_seconds * 1000))

        exp = min(self.cap_ms, self.base_ms * (2 ** max(0, attempt)))
        rand = jitter() if jitter is not None else random.random()
        delta = int(round(exp * 0.25 * (2 * rand - 1)))  # +/-25%

        return max(0, min(self.cap_ms, exp + delta))
