import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.specialists.research.report import ResearchReport


def test_defaults():
    report = ResearchReport(executive_summary="summary")

    assert report.detailed_findings == ()
    assert report.evidence == ()
    assert report.confidence == 0.0
    assert report.knowledge_gaps == ()
    assert report.recommended_next_actions == ()
    assert report.references == ()
    assert report.appendices == ()


def test_construction_with_all_fields():
    report = ResearchReport(
        executive_summary="summary",
        detailed_findings=["finding 1"],
        evidence=["evidence 1"],
        confidence=0.9,
        knowledge_gaps=["gap 1"],
        recommended_next_actions=["action 1"],
        references=["ref 1"],
        appendices=["appendix 1"],
    )

    assert report.detailed_findings == ("finding 1",)
    assert report.evidence == ("evidence 1",)
    assert report.confidence == 0.9
    assert report.knowledge_gaps == ("gap 1",)
    assert report.recommended_next_actions == ("action 1",)
    assert report.references == ("ref 1",)
    assert report.appendices == ("appendix 1",)


def test_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(ResearchReport(executive_summary="s").metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    report = ResearchReport(executive_summary="s", metadata={"a": 1})

    with pytest.raises(TypeError):
        report.metadata["a"] = 2


def test_is_frozen():
    report = ResearchReport(executive_summary="s")

    with pytest.raises(dataclasses.FrozenInstanceError):
        report.executive_summary = "changed"
