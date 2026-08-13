import dataclasses

import pytest

from app.services.ai.kernel.retry import BackoffStrategy, RetryCondition, RetryPolicy


# --- BackoffStrategy / RetryCondition --------------------------------------------


def test_backoff_strategy_values():
    assert BackoffStrategy.FIXED == "fixed"
    assert BackoffStrategy.LINEAR == "linear"
    assert BackoffStrategy.EXPONENTIAL == "exponential"
    assert BackoffStrategy.EXPONENTIAL_WITH_JITTER == "exponential_with_jitter"


def test_backoff_strategy_members_are_all_distinct():
    values = [member.value for member in BackoffStrategy]
    assert len(values) == len(set(values))


def test_retry_condition_values():
    assert RetryCondition.TRANSIENT_FAILURE == "transient_failure"
    assert RetryCondition.TIMEOUT == "timeout"
    assert RetryCondition.RATE_LIMITED == "rate_limited"
    assert RetryCondition.PROVIDER_UNAVAILABLE == "provider_unavailable"
    assert RetryCondition.ALL_FAILURES == "all_failures"


def test_retry_condition_members_are_all_distinct():
    values = [member.value for member in RetryCondition]
    assert len(values) == len(set(values))


# --- RetryPolicy -----------------------------------------------------------------


def test_retry_policy_defaults():
    policy = RetryPolicy()

    assert policy.max_attempts == 3
    assert policy.backoff_strategy == BackoffStrategy.EXPONENTIAL
    assert policy.base_delay_ms == 500
    assert policy.max_delay_ms is None
    assert policy.retry_on == (RetryCondition.TRANSIENT_FAILURE,)


def test_retry_policy_construction_with_all_fields():
    policy = RetryPolicy(
        max_attempts=5,
        backoff_strategy=BackoffStrategy.LINEAR,
        base_delay_ms=1000,
        max_delay_ms=30000,
        retry_on=(RetryCondition.RATE_LIMITED, RetryCondition.TIMEOUT),
    )

    assert policy.max_attempts == 5
    assert policy.backoff_strategy == BackoffStrategy.LINEAR
    assert policy.base_delay_ms == 1000
    assert policy.max_delay_ms == 30000
    assert policy.retry_on == (RetryCondition.RATE_LIMITED, RetryCondition.TIMEOUT)


def test_retry_policy_retry_on_is_a_tuple():
    policy = RetryPolicy()

    assert isinstance(policy.retry_on, tuple)


def test_retry_policy_is_frozen():
    policy = RetryPolicy()

    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.max_attempts = 10


def test_two_default_retry_policies_do_not_share_the_retry_on_tuple_by_mutation():
    # tuples are immutable so this is inherently safe, but confirm two
    # independently constructed default policies are equal, not aliased
    # in a way that would matter if retry_on were ever mutable
    first = RetryPolicy()
    second = RetryPolicy()

    assert first.retry_on == second.retry_on
