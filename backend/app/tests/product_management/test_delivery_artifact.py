"""DeliveryArtifact (Milestone 5) - Architecture §6's originally-approved
tenth and final memory category, added at the milestone that owns it.
Mirrors test_pm_craft_record.py's own conventions exactly."""

import pytest

from app.services.ai.agents.specialists.product_management.shared.delivery_artifact import (
    DeliveryArtifact,
    DeliveryArtifactType,
)
from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_DELIVERY_ARTIFACT


def _artifact(**overrides):
    defaults = dict(
        title="Onboarding revamp spec",
        artifact_type=DeliveryArtifactType.SPEC,
        content="Structured spec grounded in discovery evidence.",
        feature_title="Onboarding revamp",
        linked_evidence_ids=(1, 2),
    )
    defaults.update(overrides)
    return DeliveryArtifact(**defaults)


def test_requires_title():
    with pytest.raises(ValueError, match="title"):
        _artifact(title="")


def test_requires_content():
    with pytest.raises(ValueError, match="content"):
        _artifact(content="")


def test_requires_feature_title():
    with pytest.raises(ValueError, match="feature_title"):
        _artifact(feature_title="")


def test_requires_linked_evidence_ids():
    with pytest.raises(ValueError, match="linked_evidence_ids"):
        _artifact(linked_evidence_ids=())


def test_coerces_linked_evidence_ids_to_tuple():
    artifact = _artifact(linked_evidence_ids=[3, 4])
    assert artifact.linked_evidence_ids == (3, 4)


def test_memory_type_is_delivery_artifact():
    assert _artifact().memory_type == MEMORY_TYPE_DELIVERY_ARTIFACT


def test_to_memory_content_references_feature_and_evidence():
    content = _artifact().to_memory_content()
    assert "Onboarding revamp" in content
    assert "1, 2" in content
    assert "spec" in content


def test_communication_draft_artifact_type_added_at_milestone_7():
    # Milestone 7 (Stakeholder Communication Specialist) extends this
    # already-approved category with one new artifact_type member - not a
    # new memory category (ARR §3: "a Delivery-Artifact-shaped record").
    artifact = _artifact(artifact_type=DeliveryArtifactType.COMMUNICATION_DRAFT, title="Executive summary")
    assert artifact.artifact_type == DeliveryArtifactType.COMMUNICATION_DRAFT
    assert artifact.memory_type == MEMORY_TYPE_DELIVERY_ARTIFACT
    assert "communication_draft" in artifact.to_memory_content()
