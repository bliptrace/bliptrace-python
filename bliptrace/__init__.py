"""Bliptrace Python SDK — runtime error capture for the Bliptrace platform."""

from .client import Client
from .config import Config
from .envelope import build_envelope
from .retry import RetryPolicy
from .scrubber import Scrubber
from .transport import Transport, UrllibTransport

__version__ = "1.0.0"

__all__ = [
    "Client",
    "Config",
    "RetryPolicy",
    "Scrubber",
    "Transport",
    "UrllibTransport",
    "build_envelope",
    "__version__",
]
