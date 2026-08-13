from dataclasses import dataclass

from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.response import FinishReason, ProviderResponse, UsageDetails


@dataclass(frozen=True)
class ConversationResponse:
    """Normalized result of a conversation-capable provider's generate() call.

    The rest of the project depends only on this shape - never on a
    provider SDK's own response object.

    Composes ProviderResponse (provider/model/finish_reason/usage/
    raw_response - shared with every future capability's response type)
    with the one field that's actually conversation-specific: text.
    Every future capability response (vision, embeddings, ...) is
    expected to compose ProviderResponse the same way, so response
    metadata stays consistent across the whole platform instead of each
    capability inventing its own provider/model/usage fields.

    provider/model/finish_reason/usage/raw_response remain readable as
    top-level attributes via the properties below, delegating into
    `response` - existing code reading response.provider (etc.) keeps
    working even though construction now goes through the composed
    `response` field instead of five separate flat ones.

    Deliberately does NOT carry execution_id/parent_execution_id/
    correlation_id/causation_id (see M16.6). A ConversationProvider's
    generate() takes only a PromptPackage - it has no SharedExecutionContext
    and must not gain one just to stamp identity onto its own return
    value, since providers are a layer below the Runtime and are meant to
    stay ignorant of execution/agent/kernel concerns entirely (see
    base_provider.py). RuntimeResponse is the correct ownership boundary:
    it is the layer that actually holds the RuntimeContext this
    ConversationResponse was produced under, and it already composes this
    type via `RuntimeResponse.conversation_response`. An Executive that
    needs "which execution produced this ConversationResponse" reads
    RuntimeResponse.execution_id, one hop up - adding the same four
    fields here too would just be a second, redundant place for the same
    identifiers to (potentially) drift out of sync.
    """

    text: str
    response: ProviderResponse

    @property
    def provider(self) -> ProviderName:
        return self.response.metadata.provider

    @property
    def model(self) -> str:
        return self.response.metadata.model

    @property
    def finish_reason(self) -> FinishReason:
        return self.response.metadata.finish_reason

    @property
    def usage(self) -> UsageDetails | None:
        return self.response.usage

    @property
    def raw_response(self) -> object | None:
        return self.response.raw_response


@dataclass(frozen=True)
class ConversationStreamChunk:
    """One incremental piece of a streamed conversation response.

    Deliberately not a partial/optional-fields version of
    ConversationResponse: a chunk is fundamentally a different kind of
    thing (an increment, not a result), so reusing ConversationResponse
    with most fields None would blur that distinction and force every
    consumer to branch on field presence instead of the type system.

    finish_reason/usage are None on every chunk except (typically) the
    last one, matching how real streaming APIs report them.
    """

    delta: str
    provider: ProviderName
    model: str
    finish_reason: FinishReason | None = None
    usage: UsageDetails | None = None
    raw_response: object | None = None
