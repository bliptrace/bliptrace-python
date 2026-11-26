import json

from bliptrace import Config, RetryPolicy
from bliptrace.transport import UrllibTransport


class ScriptedTransport(UrllibTransport):
    """A UrllibTransport whose HTTP call and sleep are stubbed.

    ``responses`` is a list of ``(status, retry_after_seconds)`` tuples returned
    in order, one per attempt. Records every body sent and every slept delay so
    tests can assert on retries WITHOUT a real network or real sleeping.
    """

    def __init__(self, responses, policy=None):
        super().__init__(policy=policy)
        self._responses = list(responses)
        self.bodies = []
        self.slept = []

    def _attempt(self, url, body, key, timeout):
        self.bodies.append(body)
        # Default to a transport error once the script runs out.
        return self._responses.pop(0) if self._responses else (0, None)

    def _sleep_ms(self, ms):
        self.slept.append(ms)


ENVELOPE = {"event_id": "11111111-1111-4111-8111-111111111111", "level": "error"}


def _send(responses, policy=None):
    t = ScriptedTransport(responses, policy=policy)
    t.send("http://api", "k", ENVELOPE, timeout=1)
    return t


def test_stops_immediately_on_success():
    t = _send([(202, None)])
    assert len(t.bodies) == 1  # one attempt only
    assert t.slept == []  # never slept


def test_retries_then_succeeds():
    policy = RetryPolicy(max_retries=2, base_ms=100, cap_ms=2000)
    t = _send([(503, None), (202, None)], policy=policy)
    assert len(t.bodies) == 2
    # One backoff before the retry, within +/-25% of the 100ms base.
    assert len(t.slept) == 1
    assert 75 <= t.slept[0] <= 125


def test_gives_up_after_max_retries():
    policy = RetryPolicy(max_retries=2, base_ms=100, cap_ms=2000)
    # All attempts fail with 503. max_retries=2 -> 1 initial + 2 retries = 3 calls.
    t = _send([(503, None), (503, None), (503, None), (503, None)], policy=policy)
    assert len(t.bodies) == 3
    assert len(t.slept) == 2  # slept before each of the 2 retries
    # Second backoff (attempt 1, base 200ms) is larger than the first (attempt 0).
    assert all(d >= 0 for d in t.slept)


def test_does_not_retry_a_4xx():
    t = _send([(400, None), (202, None)])
    assert len(t.bodies) == 1  # 400 is not retryable -> no second attempt
    assert t.slept == []


def test_retries_a_transport_error():
    policy = RetryPolicy(max_retries=1, base_ms=50, cap_ms=2000)
    t = _send([(0, None), (202, None)], policy=policy)
    assert len(t.bodies) == 2


def test_honours_retry_after_header_in_loop():
    policy = RetryPolicy(max_retries=1, base_ms=100, cap_ms=5000)
    t = _send([(429, 2), (202, None)], policy=policy)
    assert t.slept == [2000]  # 2s Retry-After honoured, not the 100ms backoff


def test_replays_identical_body_and_event_id_across_attempts():
    policy = RetryPolicy(max_retries=2, base_ms=10, cap_ms=2000)
    t = _send([(503, None), (429, None), (202, None)], policy=policy)
    assert len(t.bodies) == 3
    # Every attempt sent byte-for-byte the same body.
    assert t.bodies[0] == t.bodies[1] == t.bodies[2]
    # ...and therefore the same event_id.
    event_ids = {json.loads(b.decode("utf-8"))["event_id"] for b in t.bodies}
    assert event_ids == {"11111111-1111-4111-8111-111111111111"}


def test_send_never_raises():
    class Boom(UrllibTransport):
        def _attempt(self, url, body, key, timeout):
            raise RuntimeError("network exploded")

    # Must not propagate -- capturing can never break the host app.
    Boom().send("http://api", "k", ENVELOPE, timeout=1)


def test_default_transport_uses_config_policy():
    # A transport built from config defaults exposes the expected policy knobs.
    cfg = Config(key="k", max_retries=5, retry_base_ms=20, retry_cap_ms=900)
    t = UrllibTransport(policy=RetryPolicy.from_config(cfg))
    assert t.policy.max_retries == 5
    assert t.policy.base_ms == 20
    assert t.policy.cap_ms == 900
