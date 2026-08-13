"""Stakeholder Communication Specialist structured outputs (Milestone 7) -
domain validation, mirroring test_discovery_outputs.py's/
test_decision_outputs.py's/test_delivery_outputs.py's/test_strategy_outputs.py's
own coverage.
"""

import pytest

from app.services.ai.agents.specialists.product_management.stakeholder_communication.outputs import (
    CommunicationAudience,
    CommunicationDraft,
    CommunicationPurpose,
    CommunicationSummary,
    DecisionExplanation,
    StakeholderMappingResult,
)


def test_audience_and_purpose_cover_every_named_example():
    audiences = {member.value for member in CommunicationAudience}
    assert {"executive", "engineering", "customer", "leadership"}.issubset(audiences)

    purposes = {member.value for member in CommunicationPurpose}
    expected = {
        "executive_summary",
        "stakeholder_update",
        "status_report",
        "roadmap_communication",
        "sprint_communication",
        "leadership_briefing",
        "product_announcement",
        "customer_communication",
        "engineering_handoff_summary",
        "meeting_followup",
        "vision_communication",
        "portfolio_communication",
    }
    assert expected.issubset(purposes)


# --- CommunicationDraft - the core "never invent facts" enforcement ------------------------------


def _draft(**overrides):
    defaults = dict(
        audience="executive",
        purpose="executive_summary",
        content="Onboarding revamp is on track.",
        assumptions=("context stable",),
        confidence=0.7,
        referenced_memory_ids=("1", "2"),
    )
    defaults.update(overrides)
    return CommunicationDraft(**defaults)


def test_draft_requires_audience():
    with pytest.raises(ValueError):
        _draft(audience="")


def test_draft_requires_purpose():
    with pytest.raises(ValueError):
        _draft(purpose="")


def test_draft_requires_content():
    with pytest.raises(ValueError):
        _draft(content="")


def test_draft_requires_non_empty_assumptions():
    with pytest.raises(ValueError):
        _draft(assumptions=())


def test_draft_requires_valid_confidence_range():
    with pytest.raises(ValueError):
        _draft(confidence=1.1)


def test_draft_requires_referenced_ids_or_explicit_gap():
    with pytest.raises(ValueError):
        _draft(referenced_memory_ids=(), evidence_gap="")


def test_draft_accepts_evidence_gap_alone():
    draft = _draft(referenced_memory_ids=(), evidence_gap="no prior findings")
    assert draft.referenced_memory_ids == ()
    assert draft.evidence_gap == "no prior findings"


def test_draft_coerces_lists_to_tuples():
    draft = _draft(supporting_evidence=["excerpt"], assumptions=["a"], referenced_memory_ids=["1"])
    assert draft.supporting_evidence == ("excerpt",)
    assert draft.assumptions == ("a",)
    assert draft.referenced_memory_ids == ("1",)


def test_draft_valid_construction_succeeds():
    draft = _draft()
    assert draft.audience == "executive"


# --- DecisionExplanation --------------------------------------------------------------------------


def _explanation(**overrides):
    defaults = dict(
        decision_title="Onboarding revamp",
        audience="leadership",
        explanation="We decided to proceed based on evidence.",
        referenced_memory_ids=("1",),
        confidence=0.7,
    )
    defaults.update(overrides)
    return DecisionExplanation(**defaults)


def test_explanation_requires_decision_title():
    with pytest.raises(ValueError):
        _explanation(decision_title="")


def test_explanation_requires_audience():
    with pytest.raises(ValueError):
        _explanation(audience="")


def test_explanation_requires_explanation_text():
    with pytest.raises(ValueError):
        _explanation(explanation="")


def test_explanation_requires_referenced_ids_or_gap():
    with pytest.raises(ValueError):
        _explanation(referenced_memory_ids=(), evidence_gap="")


def test_explanation_accepts_evidence_gap_alone():
    explanation = _explanation(referenced_memory_ids=(), evidence_gap="no decision record found")
    assert explanation.evidence_gap == "no decision record found"


def test_explanation_requires_valid_confidence_range():
    with pytest.raises(ValueError):
        _explanation(confidence=-0.1)


# --- StakeholderMappingResult ----------------------------------------------------------------------


def test_stakeholder_mapping_result_requires_name():
    with pytest.raises(ValueError):
        StakeholderMappingResult(name="")


def test_stakeholder_mapping_result_defaults():
    result = StakeholderMappingResult(name="Jane Doe")
    assert result.raci_role == ""
    assert result.role_or_interest == ""


# --- CommunicationSummary -----------------------------------------------------------------------------


def test_communication_summary_requires_summary():
    with pytest.raises(ValueError):
        CommunicationSummary(summary="")


def test_communication_summary_defaults():
    summary = CommunicationSummary(summary="2 stakeholders")
    assert summary.stakeholder_count == 0
    assert summary.draft_count == 0
