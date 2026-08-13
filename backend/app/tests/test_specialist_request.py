import dataclasses
from datetime import UTC, datetime

import pytest

from app.services.ai.agents.specialists.shared.request import SpecialistRequest


def test_defaults():
    request = SpecialistRequest(objective="Prepare for an interview")

    assert request.constraints == ()
    assert request.priority == 0
    assert request.deadline is None
    assert request.expected_output == ""
    assert request.context == ""
    assert request.tools_allowed is True
    assert request.memory_allowed is True
    assert request.web_allowed is False


def test_construction_with_all_fields():
    deadline = datetime.now(UTC)

    request = SpecialistRequest(
        objective="Compare two frameworks",
        constraints=("must cite sources",),
        priority=5,
        deadline=deadline,
        expected_output="a comparison table",
        context="the user is a backend engineer",
        tools_allowed=False,
        memory_allowed=False,
        web_allowed=True,
    )

    assert request.priority == 5
    assert request.deadline == deadline
    assert request.expected_output == "a comparison table"
    assert request.tools_allowed is False
    assert request.memory_allowed is False
    assert request.web_allowed is True


def test_constraints_is_coerced_to_a_tuple():
    request = SpecialistRequest(objective="x", constraints=["a", "b"])

    assert request.constraints == ("a", "b")


def test_is_frozen():
    request = SpecialistRequest(objective="x")

    with pytest.raises(dataclasses.FrozenInstanceError):
        request.objective = "changed"
