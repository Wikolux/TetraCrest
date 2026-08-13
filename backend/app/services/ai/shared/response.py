"""Normalized response building blocks, shared across every future AI
capability's response type.

ConversationResponse (app.services.ai.conversation.types) composes these
rather than duplicating provider/model/finish_reason/usage fields itself;
a future VisionResponse, EmbeddingResponse, etc. is expected to do the
same, so metadata stays consistent no matter which capability produced a
response.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.execution_types import Metadata


class FinishReason(StrEnum):
    """Why a provider stopped generating, normalized across vendors.

    Providers report wildly different raw values for "why did you stop"
    (OpenAI: stop/length/content_filter/tool_calls; Anthropic:
    end_turn/max_tokens/stop_sequence/tool_use; ...). A future provider
    implementation maps its own raw value onto one of these rather than
    every caller needing to know every vendor's vocabulary.
    """

    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    TOOL_CALL = "tool_call"
    ERROR = "error"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class UsageDetails:
    """Normalized token usage for one provider call.

    Distinct from (and not a replacement for) TokenUsage in
    shared/types.py, which is left exactly as it was for backward
    compatibility - nothing that used it is touched by this milestone.
    UsageDetails is the richer, composable building block
    ConversationResponse (and future capability responses) use going
    forward: it adds cached_tokens/reasoning_tokens, which several
    current-generation provider APIs already report and TokenUsage's
    narrower shape has no room for.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass(frozen=True)
class AIResponseMetadata:
    """Metadata common to every AI capability's response - not just
    conversation. provider/model identify what produced the response;
    finish_reason/latency_ms/request_id are the same shape regardless of
    whether the response came from a conversation, vision, or reasoning
    call.
    """

    provider: ProviderName
    model: str
    finish_reason: FinishReason = FinishReason.UNKNOWN
    latency_ms: float | None = None
    request_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class ProviderResponse:
    """The generic "a provider produced some output" shape.

    Every future capability response is expected to compose this (the
    way ConversationResponse does) with its own capability-specific
    payload field (text for conversation, an image reference for image
    generation, ...) rather than re-declaring metadata/usage/raw_response
    itself.
    """

    metadata: AIResponseMetadata
    usage: UsageDetails | None = None
    raw_response: object | None = None
