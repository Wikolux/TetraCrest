import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.executive.decision import Decision


def test_decision_defaults():
    decision = Decision()

    assert isinstance(decision.decision_id, str) and decision.decision_id
    assert decision.reason == ""
    assert decision.confidence == 1.0
    assert decision.requires_memory is False
    assert decision.requires_runtime is True
    assert decision.requires_delegation is False
    assert decision.requires_tools is False
    assert decision.requires_web is False
    assert decision.selected_agent is None
    assert decision.priority == 0


def test_two_decisions_get_different_ids():
    assert Decision().decision_id != Decision().decision_id


def test_decision_construction_with_all_fields():
    decision = Decision(
        reason="needs memory",
        confidence=0.8,
        requires_memory=True,
        requires_tools=True,
        requires_web=True,
        requires_delegation=True,
        selected_agent="research",
        priority=5,
    )

    assert decision.reason == "needs memory"
    assert decision.confidence == 0.8
    assert decision.requires_memory is True
    assert decision.requires_tools is True
    assert decision.requires_web is True
    assert decision.requires_delegation is True
    assert decision.selected_agent == "research"
    assert decision.priority == 5


def test_decision_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(Decision().metadata, MappingProxyType)


def test_decision_metadata_cannot_be_mutated():
    decision = Decision(metadata={"a": 1})

    with pytest.raises(TypeError):
        decision.metadata["a"] = 2


def test_decision_is_frozen():
    decision = Decision()

    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.confidence = 0.5
