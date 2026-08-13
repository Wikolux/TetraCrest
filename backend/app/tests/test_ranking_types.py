from datetime import datetime, timezone

from app.services.ranking.types import RankedCandidate, RankingCandidate


def test_ranking_candidate_construction():
    created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

    candidate = RankingCandidate(
        resource_type="memory",
        resource_id=1,
        similarity_score=0.2,
        created_at=created_at,
        metadata={"organization_id": 7},
    )

    assert candidate.resource_type == "memory"
    assert candidate.resource_id == 1
    assert candidate.similarity_score == 0.2
    assert candidate.created_at == created_at
    assert candidate.metadata == {"organization_id": 7}


def test_ranking_candidate_metadata_defaults_to_none():
    candidate = RankingCandidate(
        resource_type="memory",
        resource_id=1,
        similarity_score=0.2,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    assert candidate.metadata is None


def test_ranked_candidate_holds_candidate_and_score():
    candidate = RankingCandidate(
        resource_type="memory",
        resource_id=1,
        similarity_score=0.2,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    ranked = RankedCandidate(candidate=candidate, score=0.75)

    assert ranked.candidate is candidate
    assert ranked.score == 0.75
