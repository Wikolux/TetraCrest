import dataclasses

import pytest

from app.services.ai.agents.executive.policies import ExecutivePolicy


def test_defaults():
    policy = ExecutivePolicy()

    assert policy.maximum_depth == 5
    assert policy.maximum_retries == 3
    assert policy.maximum_runtime_seconds is None
    assert policy.allow_web is False
    assert policy.allow_tools is False
    assert policy.allow_delegation is True
    assert policy.maximum_parallel_tasks == 1


def test_construction_with_all_fields():
    policy = ExecutivePolicy(
        maximum_depth=2,
        maximum_retries=1,
        maximum_runtime_seconds=30.0,
        allow_web=True,
        allow_tools=True,
        allow_delegation=False,
        maximum_parallel_tasks=4,
    )

    assert policy.maximum_depth == 2
    assert policy.maximum_retries == 1
    assert policy.maximum_runtime_seconds == 30.0
    assert policy.allow_web is True
    assert policy.allow_tools is True
    assert policy.allow_delegation is False
    assert policy.maximum_parallel_tasks == 4


def test_is_frozen():
    policy = ExecutivePolicy()

    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.allow_web = True
