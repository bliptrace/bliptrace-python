"""The runtime Python client: decide whether to capture, build + scrub, and ship."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .config import Config
from .envelope import build_envelope
from .retry import RetryPolicy
from .scrubber import Scrubber
from .transport import Transport, UrllibTransport


class Client:
    """Runtime client. Guard-wrapped — never throws into the host app.

    Framework adapters either call :meth:`capture` directly, or split
    :meth:`build_envelope` / :meth:`send_envelope` to defer the send.
    """

    def __init__(
        self,
        config: Config,
        transport: Optional[Transport] = None,
        scrubber: Optional[Scrubber] = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibTransport(RetryPolicy.from_config(config))
        self.scrubber = scrubber or Scrubber(config.scrub_keys)

    def capture(
        self, exc: BaseException, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Capture and ship immediately."""
        envelope = self.build_envelope(exc, context)
        if envelope is not None:
            self.send_envelope(envelope)

    def build_envelope(
        self, exc: BaseException, context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Build the envelope, or ``None`` when disabled, unconfigured, or ignored."""
        try:
            if not self.config.enabled or not self.config.key:
                return None
            if self._should_ignore(exc):
                return None
            return build_envelope(exc, self.config, self.scrubber.scrub(context or {}))
        except Exception:
            return None  # never break the app

    def send_envelope(self, envelope: Dict[str, Any]) -> None:
        try:
            if self.config.key:
                self.transport.send(
                    self.config.endpoint,
                    self.config.key,
                    envelope,
                    self.config.timeout,
                )
        except Exception:
            pass  # never break the app

    def _should_ignore(self, exc: BaseException) -> bool:
        for ignored in self.config.ignore_exceptions:
            if isinstance(ignored, str):
                if type(exc).__name__ == ignored:
                    return True
            elif isinstance(exc, ignored):
                return True
        return False
