"""Immutable SDK configuration. Framework adapters build this from their config."""

from __future__ import annotations

from typing import List, Optional, Sequence, Type, Union


class Config:
    """SDK configuration. Mirrors the PHP/JS ``Config`` surface.

    ``ignore_exceptions`` may contain exception classes or their string names.
    """

    def __init__(
        self,
        key: Optional[str] = None,
        endpoint: str = "https://ingest.scope.g8suite.com",
        environment: str = "production",
        release: Optional[str] = None,
        timeout: float = 3,
        max_frames: int = 30,
        max_message: int = 2000,
        ignore_exceptions: Optional[Sequence[Union[Type[BaseException], str]]] = None,
        scrub_keys: Optional[Sequence[str]] = None,
        base_path: str = "",
        enabled: bool = True,
        sdk_name: str = "g8scope-python",
        sdk_version: str = "1.0.0",
    ) -> None:
        self.key = key
        self.endpoint = endpoint
        self.environment = environment
        self.release = release
        self.timeout = timeout
        self.max_frames = int(max_frames)
        self.max_message = int(max_message)
        self.ignore_exceptions: List[Union[Type[BaseException], str]] = list(
            ignore_exceptions or []
        )
        self.scrub_keys: List[str] = list(scrub_keys or [])
        self.base_path = base_path
        self.enabled = enabled
        self.sdk_name = sdk_name
        self.sdk_version = sdk_version
