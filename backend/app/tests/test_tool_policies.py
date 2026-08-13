import dataclasses

import pytest

from app.services.ai.kernel.retry import RetryPolicy as KernelRetryPolicy
from app.services.ai.tools.policies import RetryPolicy, ToolExecutionPolicy


def test_retry_policy_is_reused_from_the_kernel_not_redefined():
    assert RetryPolicy is KernelRetryPolicy


def test_tool_execution_policy_defaults():
    policy = ToolExecutionPolicy()

    assert policy.maximum_depth == 5
    assert policy.timeout_seconds is None
    assert isinstance(policy.retry_policy, RetryPolicy)
    assert policy.retry_policy.max_attempts == 3


def test_tool_execution_policy_construction_with_all_fields():
    retry = RetryPolicy(max_attempts=5)

    policy = ToolExecutionPolicy(maximum_depth=2, timeout_seconds=30.0, retry_policy=retry)

    assert policy.maximum_depth == 2
    assert policy.timeout_seconds == 30.0
    assert policy.retry_policy is retry


def test_is_frozen():
    policy = ToolExecutionPolicy()

    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.maximum_depth = 10
