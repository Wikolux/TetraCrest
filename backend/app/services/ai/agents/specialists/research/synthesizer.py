"""ResearchSynthesizer - the one component responsible for combining
memory, tool outputs, and a runtime response into one coherent structure.
Pure and deterministic: same inputs always produce the same
SynthesisResult, no I/O, no randomness - it only ever transforms the
arguments synthesize() is given, never fetches anything itself.
"""

from dataclasses import dataclass, field

from app.services.ai.tools.result import ToolResult
from app.services.context.types import ContextPackage


@dataclass(frozen=True)
class SynthesisResult:
    key_points: tuple[str, ...] = field(default_factory=tuple)
    sources: tuple[str, ...] = field(default_factory=tuple)
    knowledge_gaps: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for tuple_field in ("key_points", "sources", "knowledge_gaps"):
            value = getattr(self, tuple_field)
            if not isinstance(value, tuple):
                object.__setattr__(self, tuple_field, tuple(value))


class ResearchSynthesizer:
    def synthesize(
        self,
        memory_package: ContextPackage | None,
        tool_results: tuple[ToolResult, ...] = (),
        runtime_text: str | None = None,
    ) -> SynthesisResult:
        key_points: list[str] = []
        sources: list[str] = []

        if memory_package is not None:
            for section in memory_package.sections:
                for item in section.items:
                    key_points.append(item.content)
                    sources.append(f"{item.resource_type}:{item.resource_id}")

        for result in tool_results:
            if result.success and result.output is not None:
                key_points.append(str(result.output))

        if runtime_text:
            key_points.append(runtime_text)

        has_evidence = bool((memory_package is not None and memory_package.item_count > 0) or tool_results)
        knowledge_gaps = () if has_evidence else ("No memory or tool evidence was available for this objective.",)

        return SynthesisResult(
            key_points=tuple(key_points), sources=tuple(sources), knowledge_gaps=knowledge_gaps
        )
