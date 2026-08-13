from datetime import UTC, datetime

from app.services.ai.agents.specialists.research.synthesizer import ResearchSynthesizer, SynthesisResult
from app.services.ai.tools.result import ToolResult
from app.services.context.types import ContextItem, ContextPackage, ContextSection


def _package(items):
    return ContextPackage(
        sections=[ContextSection(resource_type="memory", items=items)],
        estimated_tokens=10,
        item_count=len(items),
        truncated=False,
    )


def _item(content, resource_id=1):
    return ContextItem(
        resource_type="memory", resource_id=resource_id, content=content, score=1.0, created_at=datetime.now(UTC)
    )


def test_synthesis_result_defaults():
    result = SynthesisResult()

    assert result.key_points == ()
    assert result.sources == ()
    assert result.knowledge_gaps == ()


def test_synthesis_result_tuple_fields_are_coerced():
    result = SynthesisResult(key_points=["a"], sources=["b"], knowledge_gaps=["c"])

    assert result.key_points == ("a",)
    assert result.sources == ("b",)
    assert result.knowledge_gaps == ("c",)


def test_synthesize_with_no_inputs_reports_a_knowledge_gap():
    result = ResearchSynthesizer().synthesize(None, (), None)

    assert result.key_points == ()
    assert result.knowledge_gaps != ()


def test_synthesize_extracts_memory_content_and_sources():
    package = _package([_item("fact one", resource_id=1), _item("fact two", resource_id=2)])

    result = ResearchSynthesizer().synthesize(package, (), None)

    assert result.key_points == ("fact one", "fact two")
    assert result.sources == ("memory:1", "memory:2")
    assert result.knowledge_gaps == ()


def test_synthesize_includes_successful_tool_outputs():
    tool_results = (ToolResult(success=True, output="tool finding"), ToolResult(success=False, error="failed"))

    result = ResearchSynthesizer().synthesize(None, tool_results, None)

    assert result.key_points == ("tool finding",)
    assert result.knowledge_gaps == ()


def test_synthesize_ignores_failed_tool_results_output():
    tool_results = (ToolResult(success=False, output="should not appear", error="failed"),)

    result = ResearchSynthesizer().synthesize(None, tool_results, None)

    assert result.key_points == ()


def test_synthesize_includes_runtime_text_when_given():
    result = ResearchSynthesizer().synthesize(None, (), "runtime generated text")

    assert result.key_points == ("runtime generated text",)


def test_synthesize_combines_memory_tools_and_runtime_text_in_order():
    package = _package([_item("memory fact")])
    tool_results = (ToolResult(success=True, output="tool fact"),)

    result = ResearchSynthesizer().synthesize(package, tool_results, "runtime fact")

    assert result.key_points == ("memory fact", "tool fact", "runtime fact")


def test_synthesize_is_pure_and_deterministic():
    package = _package([_item("fact")])
    tool_results = (ToolResult(success=True, output="tool fact"),)
    synthesizer = ResearchSynthesizer()

    first = synthesizer.synthesize(package, tool_results, "text")
    second = synthesizer.synthesize(package, tool_results, "text")

    assert first == second


def test_synthesize_does_not_mutate_its_inputs():
    package = _package([_item("fact")])
    original_items = list(package.sections[0].items)

    ResearchSynthesizer().synthesize(package, (), None)

    assert package.sections[0].items == original_items
