"""Discovery Specialist structured outputs (Milestone 3) - domain
validation. Mirrors Milestone 1's own test_product_management_domain_models.py
convention: every construction-time invariant is proven by test, not by
convention alone (ARR §7's own bar).
"""

import pytest

from app.services.ai.agents.specialists.product_management.discovery.outputs import (
    DiscoveryRecommendation,
    DiscoveryReport,
    DiscoverySummary,
    HypothesisItem,
    HypothesisList,
    InterviewInsights,
    InterviewSummary,
    JTBDAnalysis,
    OpportunityItem,
    OpportunityList,
    PersonaSummary,
    ProblemStatement,
)
from app.services.ai.agents.specialists.product_management.shared.discovery_finding import HypothesisStatus


# --- ProblemStatement ------------------------------------------------------------------------


def test_problem_statement_requires_statement():
    with pytest.raises(ValueError):
        ProblemStatement(statement="")


def test_problem_statement_coerces_evidence_ids_to_tuple():
    statement = ProblemStatement(statement="Users churn", evidence_ids=["42", "43"])
    assert statement.evidence_ids == ("42", "43")
    assert isinstance(statement.evidence_ids, tuple)


def test_problem_statement_defaults():
    statement = ProblemStatement(statement="Users churn")
    assert statement.target_segment == ""
    assert statement.validated is False
    assert statement.evidence_ids == ()


# --- JTBDAnalysis -----------------------------------------------------------------------------


def test_jtbd_analysis_requires_job_statement():
    with pytest.raises(ValueError):
        JTBDAnalysis(job_statement="")


def test_jtbd_analysis_holds_optional_dimensions():
    analysis = JTBDAnalysis(job_statement="hire the app to save time", functional="faster", emotional="calm", social="looks good")
    assert analysis.functional == "faster"
    assert analysis.emotional == "calm"
    assert analysis.social == "looks good"


# --- InterviewSummary / InterviewInsights ------------------------------------------------------


def test_interview_summary_requires_summary():
    with pytest.raises(ValueError):
        InterviewSummary(summary="", source="Interview #1")


def test_interview_summary_requires_source():
    with pytest.raises(ValueError):
        InterviewSummary(summary="users struggled", source="")


def test_interview_insights_requires_non_empty_insights():
    with pytest.raises(ValueError):
        InterviewInsights(insights=(), supporting_interview="Interview #1 summary")


def test_interview_insights_requires_supporting_interview():
    with pytest.raises(ValueError):
        InterviewInsights(insights=("users want speed",), supporting_interview="")


def test_interview_insights_coerces_list_to_tuple():
    insights = InterviewInsights(insights=["a", "b"], supporting_interview="summary")
    assert insights.insights == ("a", "b")


# --- PersonaSummary ----------------------------------------------------------------------------


def test_persona_summary_requires_name():
    with pytest.raises(ValueError):
        PersonaSummary(name="")


def test_persona_summary_coerces_list_fields_to_tuples():
    persona = PersonaSummary(name="Busy Ben", jobs=["ship fast"], pains=["slow tools"], goals=["grow revenue"])
    assert persona.jobs == ("ship fast",)
    assert persona.pains == ("slow tools",)
    assert persona.goals == ("grow revenue",)


# --- HypothesisItem / HypothesisList -------------------------------------------------------------


def test_hypothesis_item_requires_statement():
    with pytest.raises(ValueError):
        HypothesisItem(statement="")


def test_hypothesis_item_defaults_to_unknown_status():
    item = HypothesisItem(statement="Faster onboarding increases activation")
    assert item.status == HypothesisStatus.UNKNOWN


def test_hypothesis_list_coerces_items_to_tuple():
    items = [HypothesisItem(statement="a"), HypothesisItem(statement="b")]
    hlist = HypothesisList(items=items)
    assert isinstance(hlist.items, tuple)
    assert len(hlist.items) == 2


def test_hypothesis_list_defaults_to_empty():
    assert HypothesisList().items == ()


# --- OpportunityItem / OpportunityList -----------------------------------------------------------


def test_opportunity_item_requires_title():
    with pytest.raises(ValueError):
        OpportunityItem(title="")


def test_opportunity_list_coerces_items_to_tuple():
    items = [OpportunityItem(title="Faster onboarding")]
    olist = OpportunityList(items=items)
    assert isinstance(olist.items, tuple)


# --- DiscoveryRecommendation - the core "no fabrication" enforcement ------------------------------


def test_recommendation_requires_text():
    with pytest.raises(ValueError):
        DiscoveryRecommendation(recommendation="")


def test_recommendation_requires_evidence_or_explicit_gap():
    with pytest.raises(ValueError):
        DiscoveryRecommendation(recommendation="Build it")


def test_recommendation_accepts_evidence_ids_alone():
    rec = DiscoveryRecommendation(recommendation="Build it", evidence_ids=("42",))
    assert rec.evidence_ids == ("42",)
    assert rec.evidence_gap == ""


def test_recommendation_accepts_evidence_gap_alone():
    rec = DiscoveryRecommendation(recommendation="Not enough evidence yet", evidence_gap="No prior findings")
    assert rec.evidence_gap == "No prior findings"
    assert rec.evidence_ids == ()


def test_recommendation_coerces_evidence_ids_to_tuple():
    rec = DiscoveryRecommendation(recommendation="Build it", evidence_ids=["1", "2"])
    assert rec.evidence_ids == ("1", "2")


# --- DiscoverySummary --------------------------------------------------------------------------


def test_discovery_summary_requires_summary():
    with pytest.raises(ValueError):
        DiscoverySummary(summary="")


def test_discovery_summary_coerces_open_questions_to_tuple():
    summary = DiscoverySummary(summary="progress so far", open_questions=["is pricing validated?"])
    assert summary.open_questions == ("is pricing validated?",)


# --- DiscoveryReport ----------------------------------------------------------------------------


def test_discovery_report_requires_problem_statement():
    with pytest.raises(ValueError):
        DiscoveryReport(problem_statement="")


def test_discovery_report_coerces_list_fields_to_tuples():
    report = DiscoveryReport(
        problem_statement="Users churn",
        hypotheses=["onboarding friction"],
        evidence_gaps=["no interviews yet"],
        opportunities=["faster onboarding"],
    )
    assert report.hypotheses == ("onboarding friction",)
    assert report.evidence_gaps == ("no interviews yet",)
    assert report.opportunities == ("faster onboarding",)


def test_discovery_report_defaults():
    report = DiscoveryReport(problem_statement="Users churn")
    assert report.hypotheses == ()
    assert report.evidence_gaps == ()
    assert report.opportunities == ()
    assert report.recommendation == ""
