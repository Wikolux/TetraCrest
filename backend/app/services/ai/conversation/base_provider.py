from abc import ABC, abstractmethod
from typing import AsyncIterator, ClassVar

from app.services.ai.conversation.types import ConversationResponse, ConversationStreamChunk
from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.exceptions import StreamingError
from app.services.ai.shared.provider_metadata import ProviderMetadata
from app.services.ai.shared.types import ProviderCapabilities
from app.services.prompt_builder.types import PromptPackage


class ConversationProvider(ABC):
    """Common contract for every conversation-capable AI provider.

    A concrete provider (OpenAI, Anthropic, Gemini, Ollama, ... - none
    exist yet) turns a PromptPackage into a ConversationResponse however
    its backend requires. This is the only thing higher layers ever
    depend on - never a provider SDK's request/response objects, never a
    provider-specific parameter shape.

    Two groups of members, split deliberately by whether a "no existing
    subclass to protect" argument still holds:

    - generate(), health_check(), provider_name, model_name stay
      abstract, exactly as before - every provider must state these
      explicitly, no generic default makes sense for any of them.
    - initialize(), shutdown(), capabilities(), stream(), metadata() are
      new members added by this hardening milestone. Making them abstract
      would force every existing and future provider (including ones that
      genuinely need none of this - no persistent session, no streaming,
      no custom metadata) to write boilerplate stubs. Each gets a safe
      concrete default instead: initialize()/shutdown() no-op,
      capabilities() reports nothing supported, metadata() reports just
      the provider's name, and stream() raises StreamingError. A provider
      that needs real behavior for any of these overrides it; one that
      doesn't gets correct behavior for free, and no existing test fake
      needed to change to keep working.

    contract_version identifies which version of *this contract* a given
    provider implements. Defaults to "1.0" (this milestone's contract) so
    every provider written against today's shape doesn't need to declare
    anything; a future "v2" contract change would ship as a new default
    only providers opting into it override, so v1 providers keep working
    unmodified.
    """

    contract_version: ClassVar[str] = "1.0"

    @abstractmethod
    def generate(self, prompt_package: PromptPackage) -> ConversationResponse:
        """Generate a complete response for the given prompt.

        Must return a ConversationResponse - never a provider SDK's own
        response object, and never a raw string.
        """
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """Return whether this provider is configured and able to serve requests."""
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_name(self) -> ProviderName:
        """Return this provider's identity."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the identifier of the model this provider is configured to use."""
        raise NotImplementedError

    def initialize(self) -> None:
        """Perform any setup needed before this provider can serve
        requests - opening a persistent HTTP session, warming a
        connection pool, starting a local inference engine, allocating a
        GPU, spinning up a background worker, and so on.

        Concrete default: no-op. Most providers need nothing here;
        override when real setup is required. The kernel/factory calling
        this doesn't need to know which case applies.
        """
        return None

    def shutdown(self) -> None:
        """Release whatever initialize() acquired.

        Concrete default: no-op, mirroring initialize().
        """
        return None

    def capabilities(self) -> ProviderCapabilities:
        """Return what this provider/model combination can actually do.

        Concrete default: ProviderCapabilities() - the all-conservative
        "nothing declared" value. Override to declare real capabilities;
        never assume a capability a provider hasn't explicitly declared.
        """
        return ProviderCapabilities()

    def metadata(self) -> ProviderMetadata:
        """Return descriptive metadata about this provider.

        Concrete default: a minimal ProviderMetadata built from just
        provider_name. Override for vendor/homepage/license/
        context_window/etc.
        """
        return ProviderMetadata(provider_name=str(self.provider_name))

    async def stream(self, prompt_package: PromptPackage) -> AsyncIterator[ConversationStreamChunk]:
        """Stream a response incrementally as ConversationStreamChunks.

        An AsyncIterator, not a synchronous Iterator: this is a FastAPI
        (async) application, and a provider streaming real tokens over
        HTTP will use an async HTTP client - a synchronous Iterator would
        force blocking I/O onto the event loop for the whole request.
        Choosing AsyncIterator now means no future streaming provider
        needs a breaking signature change to add real streaming.

        Concrete default: raises StreamingError, since not every
        provider supports streaming. Check
        capabilities().supports_streaming before calling, or catch
        StreamingError. A provider that supports streaming overrides
        this with a real async generator; one that doesn't gets correct
        behavior with no boilerplate.
        """
        raise StreamingError(f"{self.provider_name} does not support streaming")
        yield  # pragma: no cover - unreachable; keeps this a valid async generator
