from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.context.context_builder import ContextBuilder
from app.services.context.pipeline import ContextPipeline
from app.services.context.stages.base_stage import PipelineStage
from app.services.context.types import ContextPackage

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


@dataclass
class _FakeRankedResult:
    """Matches the RankedResult Protocol structurally - no import from
    app.services.ranking needed."""

    resource_type: str
    resource_id: int
    content: str
    score: float
    created_at: datetime
    metadata: dict | None = None


def _result(resource_id, content="content", resource_type="memory", score=0.5, created_at=_NOW, metadata=None):
    return _FakeRankedResult(
        resource_type=resource_type,
        resource_id=resource_id,
        content=content,
        score=score,
        created_at=created_at,
        metadata=metadata,
    )


# --- basic conversion / ContextPackage correctness --------------------------


def test_build_returns_a_context_package():
    builder = ContextBuilder()

    package = builder.build([_result(1)])

    assert isinstance(package, ContextPackage)


def test_build_converts_ranked_results_into_context_items_correctly():
    builder = ContextBuilder()
    result = _result(1, content="hello world", resource_type="memory", score=0.9, metadata={"organization_id": 7})

    package = builder.build([result])

    item = package.sections[0].items[0]
    assert item.resource_type == "memory"
    assert item.resource_id == 1
    assert item.content == "hello world"
    assert item.score == 0.9
    assert item.created_at == _NOW
    assert item.metadata == {"organization_id": 7}


def test_empty_input_produces_an_empty_untruncated_package():
    builder = ContextBuilder()

    package = builder.build([])

    assert package.sections == []
    assert package.item_count == 0
    assert package.estimated_tokens == 0
    assert package.truncated is False


def test_single_item_is_hydrated_into_a_single_section():
    builder = ContextBuilder()

    package = builder.build([_result(1, content="a" * 8)])

    assert package.item_count == 1
    assert len(package.sections) == 1
    assert package.sections[0].resource_type == "memory"
    assert package.estimated_tokens == 2  # 8 // 4


# --- duplicate removal (end to end) -----------------------------------------


def test_build_removes_exact_duplicates():
    builder = ContextBuilder()
    results = [_result(1, content="first"), _result(1, content="second")]

    package = builder.build(results)

    assert package.item_count == 1
    assert package.sections[0].items[0].content == "first"


# --- budget / truncation (end to end) ---------------------------------------


def test_build_respects_max_tokens_and_reports_truncation():
    builder = ContextBuilder()
    results = [_result(1, content="a" * 40), _result(2, content="a" * 40), _result(3, content="a" * 40)]

    package = builder.build(results, max_tokens=15)  # room for exactly one 10-token item

    assert package.item_count == 1
    assert package.truncated is True
    assert package.estimated_tokens == 10


def test_build_reports_no_truncation_when_everything_fits():
    builder = ContextBuilder()
    results = [_result(1, content="a" * 8), _result(2, content="a" * 8)]

    package = builder.build(results, max_tokens=4000)

    assert package.truncated is False
    assert package.item_count == 2


# --- grouping / mixed resource types (end to end) ---------------------------


def test_build_groups_mixed_resource_types_into_separate_sections():
    results = [
        _result(1, resource_type="memory"),
        _result(2, resource_type="conversation_message"),
        _result(3, resource_type="memory"),
    ]
    builder = ContextBuilder()

    package = builder.build(results)

    sections_by_type = {section.resource_type: section.items for section in package.sections}
    assert set(sections_by_type.keys()) == {"memory", "conversation_message"}
    assert [item.resource_id for item in sections_by_type["memory"]] == [1, 3]
    assert [item.resource_id for item in sections_by_type["conversation_message"]] == [2]


# --- ranking order preservation ----------------------------------------------


def test_build_preserves_ranking_order_within_each_group():
    # results are already ranked (best first) by the time ContextBuilder
    # receives them - it must not re-sort by anything
    results = [
        _result(3, resource_type="memory", score=0.9),
        _result(1, resource_type="memory", score=0.5),
        _result(2, resource_type="memory", score=0.1),
    ]
    builder = ContextBuilder()

    package = builder.build(results)

    assert [item.resource_id for item in package.sections[0].items] == [3, 1, 2]


# --- stage injection ----------------------------------------------------------


def test_injected_pipeline_is_used_instead_of_the_default_one():
    class _StubStage(PipelineStage):
        def process(self, data):
            return "stub result"

    pipeline = ContextPipeline([_StubStage()])
    builder = ContextBuilder(pipeline=pipeline)

    result = builder.build([_result(1)])

    assert result == "stub result"


def test_injected_pipeline_receives_the_converted_context_items():
    received = {}

    class _CapturingStage(PipelineStage):
        def process(self, data):
            received["items"] = data
            return data

    pipeline = ContextPipeline([_CapturingStage()])
    builder = ContextBuilder(pipeline=pipeline)

    builder.build([_result(1, content="hello")])

    assert len(received["items"]) == 1
    assert received["items"][0].content == "hello"


def test_default_pipeline_runs_all_four_standard_stages_in_order():
    from app.services.context.stages.budget_stage import BudgetStage
    from app.services.context.stages.duplicate_stage import DuplicateStage
    from app.services.context.stages.formatter_stage import FormatterStage
    from app.services.context.stages.grouping_stage import GroupingStage

    builder = ContextBuilder()
    pipeline = builder._default_pipeline(max_tokens=4000)

    stage_types = [type(stage) for stage in pipeline.stages]
    assert stage_types == [DuplicateStage, BudgetStage, GroupingStage, FormatterStage]


def test_default_pipeline_budget_stage_uses_the_given_max_tokens():
    from app.services.context.stages.budget_stage import BudgetStage

    builder = ContextBuilder()
    pipeline = builder._default_pipeline(max_tokens=123)

    budget_stage = next(stage for stage in pipeline.stages if isinstance(stage, BudgetStage))
    assert budget_stage.max_tokens == 123
