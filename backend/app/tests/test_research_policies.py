import dataclasses

import pytest

from app.services.ai.agents.specialists.research.policies import ResearchPolicy


def test_defaults():
    policy = ResearchPolicy()

    assert policy.maximum_sources == 10
    assert policy.minimum_confidence == 0.0
    assert policy.require_evidence is False


def test_construction_with_all_fields():
    policy = ResearchPolicy(maximum_sources=3, minimum_confidence=0.5, require_evidence=True)

    assert policy.maximum_sources == 3
    assert policy.minimum_confidence == 0.5
    assert policy.require_evidence is True


def test_is_frozen():
    policy = ResearchPolicy()

    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.minimum_confidence = 1.0
