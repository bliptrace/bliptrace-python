import re

from g8scope import Client, Config, Transport

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class FakeTransport(Transport):
    """Records sent envelopes; no network."""

    def __init__(self):
        self.sent = []

    def send(self, endpoint, key, envelope, timeout):
        self.sent.append(
            {
                "endpoint": endpoint,
                "key": key,
                "envelope": envelope,
                "timeout": timeout,
            }
        )


def _raise(exc):
    """Raise then return the exception with a real traceback attached."""
    try:
        raise exc
    except BaseException as e:  # noqa: BLE001
        return e


def test_builds_and_ships_a_valid_envelope():
    t = FakeTransport()
    client = Client(
        Config(key="k", endpoint="http://api", base_path="/srv/app"), t
    )
    client.capture(_raise(RuntimeError("boom")))

    assert len(t.sent) == 1
    env = t.sent[0]["envelope"]
    assert env["schema_version"] == "1.0"
    assert UUID_RE.match(env["event_id"])
    assert env["runtime"]["name"] == "python"
    assert env["runtime"]["version"]
    assert env["sdk"]["name"] == "g8scope-python"
    assert env["level"] == "error"
    assert env["exception"]["type"] == "RuntimeError"
    assert env["exception"]["message"] == "boom"
    frame = env["exception"]["frames"][0]
    assert set(frame.keys()) == {"file", "line", "function", "in_app"}


def test_ignores_configured_exception_types_by_class():
    t = FakeTransport()
    Client(Config(key="k", ignore_exceptions=[ValueError]), t).capture(
        _raise(ValueError("noise"))
    )
    assert t.sent == []


def test_ignores_configured_exception_types_by_name():
    t = FakeTransport()
    Client(Config(key="k", ignore_exceptions=["KeyError"]), t).capture(
        _raise(KeyError("noise"))
    )
    assert t.sent == []


def test_does_nothing_without_a_key():
    t = FakeTransport()
    Client(Config(key=None), t).capture(_raise(Exception("x")))
    assert t.sent == []


def test_does_nothing_when_disabled():
    t = FakeTransport()
    Client(Config(key="k", enabled=False), t).capture(_raise(Exception("x")))
    assert t.sent == []


def test_scrubs_sensitive_context_before_sending():
    t = FakeTransport()
    Client(Config(key="k", scrub_keys=["password"]), t).capture(
        _raise(Exception("x")),
        {"user": {"password": "hunter2", "id": "7"}},
    )
    ctx = t.sent[0]["envelope"]["context"]
    assert ctx["user"]["password"] == "[REDACTED]"
    assert ctx["user"]["id"] == "7"


def test_scrub_is_case_insensitive_and_recursive():
    t = FakeTransport()
    Client(Config(key="k", scrub_keys=["secret"]), t).capture(
        _raise(Exception("x")),
        {"custom": {"nested": {"SECRET": "abc", "ok": 1}}},
    )
    ctx = t.sent[0]["envelope"]["context"]
    assert ctx["custom"]["nested"]["SECRET"] == "[REDACTED]"
    assert ctx["custom"]["nested"]["ok"] == 1


def test_never_raises_even_if_context_is_weird():
    t = FakeTransport()
    client = Client(Config(key="k"), t)
    # A non-serialisable / odd value must not blow up capture.
    client.capture(_raise(Exception("x")), {"a": lambda: 1, "b": object()})
    # Must not raise; envelope may or may not send, but no exception escapes.


def test_message_is_truncated_to_max_message():
    t = FakeTransport()
    Client(Config(key="k", max_message=5), t).capture(_raise(Exception("0123456789")))
    assert t.sent[0]["envelope"]["exception"]["message"] == "01234"


def test_occurred_at_has_millisecond_precision():
    t = FakeTransport()
    Client(Config(key="k"), t).capture(_raise(Exception("x")))
    occurred_at = t.sent[0]["envelope"]["occurred_at"]
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", occurred_at)


def test_project_is_never_in_payload():
    t = FakeTransport()
    Client(Config(key="k"), t).capture(_raise(Exception("x")))
    assert "project" not in t.sent[0]["envelope"]
