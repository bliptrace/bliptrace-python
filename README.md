# Bliptrace Python SDK

The runtime Python SDK for [Bliptrace](https://scope.g8suite.com) — a multi-tenant
error-capture and observability platform. The SDK turns a native Python exception
into the language-neutral Bliptrace **error envelope** and ships it to the ingest API.

It does four things, and is designed to **never throw into your application**:

1. Build the envelope from a caught exception (using the standard `traceback` module).
2. Scrub PII — recursively redact configured keys (case-insensitive) in the context.
3. Ship the envelope over HTTPS using only the Python standard library (no third-party HTTP dependency).
4. Stay lean — it has **no runtime dependencies**.

## Installation

```bash
pip install bliptrace
```

Requires Python 3.8 or newer.

## Usage

```python
from bliptrace import Client, Config

client = Client(Config(
    key="your-ingest-key",
    environment="production",
    release="my-app@2026.06.25",
    base_path="/srv/app",            # frames under this path are marked in_app
    scrub_keys=["password", "token", "authorization"],
    ignore_exceptions=[KeyboardInterrupt],  # classes or class-name strings
))

try:
    do_something_risky()
except Exception as exc:
    client.capture(exc, context={
        "request": {"method": "POST", "url": "/checkout"},
        "user": {"id": "u_123", "password": "hunter2"},  # password gets redacted
        "custom": {"order_id": "ord_42"},
    })
```

### Deferring the send

Adapters that want to flush after the response has been sent can split the two steps:

```python
envelope = client.build_envelope(exc, context)
if envelope is not None:
    # ... later ...
    client.send_envelope(envelope)
```

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `key` | `None` | Ingest key. No key means nothing is sent. |
| `endpoint` | `https://ingest.scope.g8suite.com` | Ingest base URL; the SDK POSTs to `{endpoint}/v1/ingest`. |
| `environment` | `production` | Environment marker. |
| `release` | `None` | Release marker, e.g. `my-app@2026.06.25`. |
| `timeout` | `3` | HTTP timeout in seconds. |
| `max_frames` | `30` | Maximum stack frames captured. |
| `max_message` | `2000` | Exception message truncation length. |
| `ignore_exceptions` | `[]` | Exception classes or class-name strings to skip. |
| `scrub_keys` | `[]` | Context keys to redact (case-insensitive). |
| `base_path` | `""` | Frames whose file starts with this path (and are not in site-packages) are `in_app`. |
| `enabled` | `True` | Master switch. |
| `sdk_name` | `bliptrace-python` | Reported SDK name. |
| `sdk_version` | `1.0.0` | Reported SDK version. |

## A note on the project / tenant

You never put a `project` in the payload. The Bliptrace server resolves the project
**server-side from the ingest key**, so a client cannot spoof another tenant. The
key is the only thing that binds telemetry to a project.

## Testing

```bash
pip install pytest
python3 -m pytest -q
```

The test suite uses a fake transport that records envelopes in memory — no network
is touched.

## Licence

MIT — see [LICENSE](LICENSE). Copyright (c) Developers Hub Sdn Bhd.
