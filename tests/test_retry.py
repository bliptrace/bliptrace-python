import pytest

from g8scope import Config, RetryPolicy


@pytest.mark.parametrize(
    "status,expected",
    [
        (0, True),  # transport error / timeout
        (408, True),  # request timeout
        (429, True),  # too many requests
        (500, True),
        (502, True),  # bad gateway
        (503, True),  # service unavailable
        (200, False),  # ok
        (202, False),  # accepted
        (400, False),  # bad request
        (403, False),  # forbidden
        (404, False),
        (418, False),
    ],
)
def test_classifies_retryable_statuses(status, expected):
    assert RetryPolicy(max_retries=5).is_retryable(status) is expected


def test_stops_retrying_once_attempt_cap_is_reached():
    policy = RetryPolicy(max_retries=2)
    assert policy.should_retry(503, 0) is True
    assert policy.should_retry(503, 1) is True
    assert policy.should_retry(503, 2) is False  # exhausted


def test_never_retries_a_non_retryable_status_even_with_attempts_left():
    policy = RetryPolicy(max_retries=5)
    assert policy.should_retry(400, 0) is False
    assert policy.should_retry(200, 0) is False


def test_backoff_grows_exponentially_and_is_capped():
    policy = RetryPolicy(base_ms=100, cap_ms=2000)
    no_jitter = lambda: 0.5  # noqa: E731 -- 2*0.5-1 = 0 -> no jitter

    assert policy.delay_ms(0, jitter=no_jitter) == 100
    assert policy.delay_ms(1, jitter=no_jitter) == 200
    assert policy.delay_ms(2, jitter=no_jitter) == 400
    assert policy.delay_ms(3, jitter=no_jitter) == 800
    assert policy.delay_ms(8, jitter=no_jitter) == 2000  # capped


def test_jitter_stays_within_plus_minus_25_percent():
    policy = RetryPolicy(base_ms=100, cap_ms=100000)
    for jitter in (lambda: 0.0, lambda: 0.999, lambda: 0.5):
        d = policy.delay_ms(3, jitter=jitter)  # base 800ms
        assert 600 <= d <= 1000


def test_jitter_is_clamped_to_zero_and_cap():
    # Even with extreme draws the result never goes negative or exceeds the cap.
    policy = RetryPolicy(base_ms=100, cap_ms=2000)
    assert policy.delay_ms(0, jitter=lambda: 0.0) >= 0
    assert policy.delay_ms(20, jitter=lambda: 0.999) <= 2000


def test_retry_after_is_honoured_and_capped():
    policy = RetryPolicy(cap_ms=5000)
    assert policy.delay_ms(0, retry_after_seconds=2) == 2000  # 2s honoured
    assert policy.delay_ms(0, retry_after_seconds=999) == 5000  # hostile value capped


def test_retry_after_ignored_when_not_positive():
    policy = RetryPolicy(base_ms=100, cap_ms=2000)
    # Falls back to exponential backoff when Retry-After is zero/None.
    assert policy.delay_ms(1, retry_after_seconds=0, jitter=lambda: 0.5) == 200
    assert policy.delay_ms(1, retry_after_seconds=None, jitter=lambda: 0.5) == 200


def test_builds_from_sdk_config():
    policy = RetryPolicy.from_config(
        Config(key="k", max_retries=7, retry_base_ms=50, retry_cap_ms=9000)
    )
    assert policy.max_retries == 7
    assert policy.base_ms == 50
    assert policy.cap_ms == 9000


def test_config_defaults():
    c = Config(key="k")
    assert c.max_retries == 2
    assert c.retry_base_ms == 100
    assert c.retry_cap_ms == 2000
