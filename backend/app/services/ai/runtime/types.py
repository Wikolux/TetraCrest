"""Core value objects for the AI Runtime - the kernel that executes every
AI capability request against a provider resolved through
ConversationProviderFactory.

Unlike the earlier, deliberately capability-agnostic runtime engine this
package replaces, the Runtime is now explicitly coupled to the AI
Platform's conversation capability (PromptPackage in, ConversationResponse
out) - never to a specific vendor. It knows ConversationProviderFactory
and ConversationProvider; it must never know any individual vendor by name.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping

from app.services.ai.conversation.types import ConversationResponse
from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.events import GenericEvent, hash_event
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.shared.execution_metadata import ExecutionMetadata
from app.services.ai.shared.response import UsageDetails
from app.services.prompt_builder.types import PromptPackage

if TYPE_CHECKING:
    from app.services.ai.runtime.cancellation import CancellationToken

Metadata = Mapping[str, Any]


class AIRuntimeError(Exception):
    """Root exception for the Runtime layer."""


def _freeze_mapping(instance, field_name: str) -> None:
    value = getattr(instance, field_name)
    if not isinstance(value, MappingProxyType):
        object.__setattr__(instance, field_name, MappingProxyType(dict(value)))


class EventType(StrEnum):
    """Every kind of event the Runtime can emit for one execution."""

    STARTED = "started"
    PROVIDER_SELECTED = "provider_selected"
    REQUEST_SENT = "request_sent"
    RESPONSE_RECEIVED = "response_received"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass(frozen=True, kw_only=True)
class RuntimeEvent(GenericEvent):
    """One point-in-time occurrence during an execution.

    A single typed shape carrying an EventType discriminator rather than
    one dataclass per event kind - every event the Runtime emits (Started,
    Provider Selected, ..., Timeout) needs exactly the same fields
    (which execution, when, and freeform detail), so a zoo of near-
    identical classes would add nothing a `data` mapping doesn't already
    cover.

    Built on GenericEvent (app.services.ai.shared.events) - correlation_id
    is a new attribute gained through that base (defaulting to execution_id,
    same as every other event type), not something RuntimeEvent tracked
    before; every previously-existing field/behavior is unchanged.
    """

    event_type: EventType

    __hash__ = hash_event


@dataclass(frozen=True)
class RuntimeContext:
    """Tracks identity and progress of one execution as it moves through
    the Runtime: middleware, provider resolution, retries.

    Composes SharedExecutionContext (app.services.ai.shared.execution_context)
    rather than redefining execution identity itself - `shared` is the one
    place execution_id/request_id/correlation_id/.../metadata live;
    everything declared directly on this class is genuinely Runtime-
    specific (which provider/model, which attempt, how long to wait).
    execution_id/request_id/metadata remain readable as
    `context.execution_id` etc. via the properties below, delegating into
    `shared`, so existing code reading them keeps working unchanged even
    though they're no longer fields of RuntimeContext itself.

    Frozen like every other value object here - a new attempt is
    represented by `dataclasses.replace(context, attempt=...)`, never by
    mutating attempt in place, so a context handed to a hook or middleware
    can never be changed out from under it later.
    """

    shared: SharedExecutionContext = field(default_factory=SharedExecutionContext)
    provider: ProviderName | None = None
    provider_model: str | None = None
    attempt: int = 1
    retry_count: int = 0
    timeout: float | None = None
    runtime_metadata: ExecutionMetadata = field(default_factory=ExecutionMetadata)

    @property
    def execution_id(self) -> str:
        return self.shared.execution_id

    @property
    def request_id(self) -> str:
        return self.shared.request_id

    @property
    def parent_execution_id(self) -> str | None:
        return self.shared.parent_execution_id

    @property
    def correlation_id(self) -> str:
        return self.shared.correlation_id

    @property
    def causation_id(self) -> str | None:
        return self.shared.causation_id

    @property
    def metadata(self) -> Metadata:
        return self.shared.metadata


@dataclass(frozen=True)
class RuntimeRequest:
    """A request to execute one conversation-capability call through the
    Runtime.

    provider names WHICH provider to resolve via ConversationProviderFactory
    - the Runtime never hardcodes a vendor. cancellation_token is a mutable
    handle (see cancellation.py) held by reference inside this otherwise
    immutable request: freezing the request prevents reassigning the field
    itself, not the token signalling cancellation through it, which is the
    whole point of a cooperative cancellation token.

    parent_shared lets a caller that already has its own SharedExecutionContext
    (an agent's AgentContext.shared, a kernel ExecutionContext.shared, ...)
    propagate it into the Runtime call as the parent of a new child
    execution (see SharedExecutionContext.child()) - this is what actually
    makes "Executive -> Agent -> Runtime" one execution tree with one
    shared correlation_id in practice, not just a capability that exists
    in isolation on SharedExecutionContext itself. None (the default)
    means this request starts a fresh, unrelated execution tree of its own.
    """

    organization_id: int
    prompt_package: PromptPackage
    provider: ProviderName
    conversation_id: int | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    timeout: float | None = None
    cancellation_token: "CancellationToken | None" = None
    parent_shared: SharedExecutionContext | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_mapping(self, "metadata")


@dataclass(frozen=True)
class RuntimeExecutionResult:
    """The outcome of a single execution attempt.

    Internal to RuntimeExecutor: retry orchestration produces one of these
    per attempt before deciding whether to retry, and the last attempt's
    result becomes the basis for the RuntimeResponse the caller actually
    sees. Distinct from RuntimeResponse, which is the single, public,
    whole-execution result (aggregating every attempt's events, not just
    the last attempt's outcome).

    retryable distinguishes failures worth retrying (a provider call that
    raised, a timeout) from ones that never will (the provider name itself
    can't be resolved) - retrying the latter would just fail identically
    every time.
    """

    success: bool
    conversation_response: ConversationResponse | None = None
    error: str | None = None
    attempt: int = 1
    duration_ms: float = 0.0
    retryable: bool = True


@dataclass(frozen=True)
class RuntimeResponse:
    """The Runtime's public, single result for one RuntimeRequest.

    Always returned by AIRuntime.execute() - a provider, timeout, or
    cancellation failure is reported here via success=False/error, never
    raised as an exception, matching how every other execution engine in
    this platform behaves.

    execution_id/parent_execution_id/correlation_id/causation_id are
    copied directly from the RuntimeContext.shared that produced this
    response (via SharedExecutionContext.identity_fields(), never derived
    by inspecting `events`) - an Executive can answer "which execution
    produced this response" from the response alone, without walking its
    event list. execution_id/correlation_id default to a fresh uuid4 each
    (matching SharedExecutionContext's own defaulting) only so a
    RuntimeResponse remains constructible without a context in tests;
    RuntimeExecutor always supplies real ones from the context it ran.
    """

    success: bool
    provider: ProviderName | None = None
    conversation_response: ConversationResponse | None = None
    latency_ms: float = 0.0
    usage: UsageDetails | None = None
    events: tuple[RuntimeEvent, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_execution_id: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_mapping(self, "metadata")
