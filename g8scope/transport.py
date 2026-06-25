"""Ships an envelope to the ingest API. Implementations must never throw."""

from __future__ import annotations

import json
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict


class Transport(ABC):
    """Transport contract. ``send`` must never raise into the host app."""

    @abstractmethod
    def send(
        self, endpoint: str, key: str, envelope: Dict[str, Any], timeout: float
    ) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class UrllibTransport(Transport):
    """Dependency-free transport using the stdlib ``urllib.request``."""

    def send(
        self, endpoint: str, key: str, envelope: Dict[str, Any], timeout: float
    ) -> None:
        try:
            url = endpoint.rstrip("/") + "/v1/ingest"
            body = json.dumps(envelope).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-Ingest-Key": key,
                },
            )
            with urllib.request.urlopen(req, timeout=max(0.001, timeout)):
                pass
        except Exception:
            # Capturing must never break the monitored app.
            pass
