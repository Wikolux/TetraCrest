import dataclasses

import pytest

from app.services.ai.agents.policies import ExecutionPolicy, PermissionPolicy, RetryPolicy, TimeoutPolicy
from app.services.ai.kernel.retry import RetryPolicy as KernelRetryPolicy


def test_retry_policy_is_reused_from_the_kernel_not_redefined():
    assert RetryPolicy is KernelRetryPolicy


def test_permission_policy_defaults():
    policy = PermissionPolicy()

    assert policy.required_permissions == ()
    assert policy.allow_all is False
    assert policy.deny_all is False


def test_permission_policy_is_frozen():
    policy = PermissionPolicy()

    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.allow_all = True


def test_execution_policy_defaults():
    policy = ExecutionPolicy()

    assert policy.max_concurrent_executions == 1
    assert policy.allow_reentrant is False


def test_execution_policy_is_frozen():
    policy = ExecutionPolicy()

    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.max_concurrent_executions = 5


def test_timeout_policy_defaults_to_no_timeout():
    policy = TimeoutPolicy()

    assert policy.timeout_seconds is None


def test_timeout_policy_is_frozen():
    policy = TimeoutPolicy(timeout_seconds=30)

    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.timeout_seconds = 60
