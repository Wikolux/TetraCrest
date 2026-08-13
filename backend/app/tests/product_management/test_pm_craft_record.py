"""PMCraftRecord (Milestone 4) - Architecture §6/§13's originally-approved
PM Craft Record category, added at the milestone that owns it. Mirrors
Milestone 1's own domain-model test conventions exactly."""

import pytest

from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework
from app.services.ai.agents.specialists.product_management.shared.pm_craft_record import PMCraftRecord
from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_PM_CRAFT_RECORD


def test_requires_decision_title():
    with pytest.raises(ValueError, match="decision_title"):
        PMCraftRecord(framework=DecisionFramework.RICE, decision_title="")


def test_memory_type_is_pm_craft_record():
    record = PMCraftRecord(framework=DecisionFramework.RICE, decision_title="Onboarding revamp")
    assert record.memory_type == MEMORY_TYPE_PM_CRAFT_RECORD


def test_to_memory_content_names_framework_and_decision():
    record = PMCraftRecord(framework=DecisionFramework.ICE, decision_title="Sunset legacy API", evidence_count=3)
    content = record.to_memory_content()
    assert "ice" in content
    assert "Sunset legacy API" in content
    assert "3" in content


def test_evidence_count_defaults_to_zero_and_is_omitted_when_absent():
    record = PMCraftRecord(framework=DecisionFramework.KANO, decision_title="Add dark mode")
    assert record.evidence_count == 0
    assert "supporting evidence" not in record.to_memory_content()
