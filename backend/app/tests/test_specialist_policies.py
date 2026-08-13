import dataclasses

import pytest

from app.services.ai.agents.specialists.shared.policies import RetryPolicy, SpecialistExecutionPolicy
from app.services.ai.kernel.retry import RetryPolicy as KernelRetryPolicy


def test_retry_policy_is_reused_from_the_kernel_not_redefined():
    assert RetryPolicy is KernelRetryPolicy


def test_defaults():
    policy = SpecialistExecutionPolicy()

    assert policy.maximum_depth == 5
    assert policy.timeout_seconds is None
    assert isinstance(policy.retry_policy, RetryPolicy)
    assert policy.allow_delegation is True


def test_construction_with_all_fields():
    retry = RetryPolicy(max_attempts=5)

    policy = SpecialistExecutionPolicy(
        maximum_depth=2, timeout_seconds=30.0, retry_policy=retry, allow_delegation=False
    )

    assert policy.maximum_depth == 2
    assert policy.timeout_seconds == 30.0
    assert policy.retry_policy is retry
    assert policy.allow_delegation is False


def test_is_frozen():
    policy = SpecialistExecutionPolicy()

    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.maximum_depth = 10
