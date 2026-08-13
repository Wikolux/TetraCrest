"""AIRuntime - the sole public entry point for executing AI capability
requests.

Every future agent is meant to call AIRuntime rather than reaching into a
provider, the executor, or the middleware pipeline directly - that is the
entire reason this façade exists. AIRuntime itself knows only
ConversationProviderFactory/ConversationProviderRegistry/ProviderName; it
must never import or branch on any individual vendor.
"""

from typing import AsyncIterator

from app.services.ai.conversation.provider_factory import ConversationProviderFactory
from app.services.ai.conversation.registry import ConversationProviderRegistry
from app.services.ai.conversation.types import ConversationStreamChunk
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.events import RuntimeEventPublisher
from app.services.ai.runtime.execution import RuntimeExecutor
from app.services.ai.runtime.hooks import RuntimeHook
from app.services.ai.runtime.middleware import RuntimeMiddleware
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse
from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.provider_config import ConversationProviderConfig
from app.services.ai.shared.types import ProviderCapabilities


class AIRuntime:
    """The kernel that executes every AI capability request.

    Providers never execute themselves and agents never call providers
    directly - everything goes through execute()/execute_stream(). health(),
    capabilities(), and providers() are read-only introspection over
    whatever ConversationProviderRegistry currently holds, useful to an
    ops surface or a future agent deciding which provider to request.

    Constructor injection throughout: pass a pre-built executor for full
    control over wiring (tests do this), or pass middleware/hooks/
    max_retries and get a correctly-wired default executor for free.
    """

    def __init__(
        self,
        middleware: tuple[RuntimeMiddleware, ...] = (),
        hooks: tuple[RuntimeHook, ...] = (),
        event_publisher: RuntimeEventPublisher | None = None,
        max_retries: int = 0,
        executor: RuntimeExecutor | None = None,
    ) -> None:
        self.executor = executor or RuntimeExecutor(
            middleware=middleware,
            hooks=hooks,
            event_publisher=event_publisher,
            max_retries=max_retries,
        )

    def execute(self, request: RuntimeRequest) -> RuntimeResponse:
        return self.executor.execute(request)

    async def execute_stream(self, request: RuntimeRequest) -> AsyncIterator[ConversationStreamChunk]:
        """Stream a response incrementally via the resolved provider's stream().

        Deliberately lighter-weight than execute(): no retry orchestration
        (retrying a partially-consumed stream has no well-defined
        semantics) and no middleware pipeline (RuntimeMiddleware's
        contract is a synchronous request/response call, not a fit for
        incremental chunks). Cancellation is still honored between chunks.
        A provider-resolution or streaming failure propagates directly to
        the caller - a stream consumer is expected to handle errors around
        its `async for`, not via a returned success flag.
        """
        provider = ConversationProviderFactory.create(request.provider, self._build_config(request))
        async for chunk in provider.stream(request.prompt_package):
            if request.cancellation_token is not None and request.cancellation_token.cancelled():
                return
            yield chunk

    def health(self) -> dict[ProviderName, bool]:
        """Report health for every currently registered provider.

        A provider that fails to construct or whose health_check() raises
        is reported unhealthy rather than propagating the failure - a
        health report must never itself crash on a broken provider.
        """
        report: dict[ProviderName, bool] = {}
        for provider_name in ConversationProviderRegistry.all_registered():
            try:
                provider = ConversationProviderFactory.create(provider_name)
                report[provider_name] = provider.health_check()
            except Exception:  # noqa: BLE001 - a health report must never raise
                report[provider_name] = False
        return report

    def capabilities(self) -> dict[ProviderName, ProviderCapabilities]:
        """Report declared capabilities for every currently registered provider."""
        report: dict[ProviderName, ProviderCapabilities] = {}
        for provider_name in ConversationProviderRegistry.all_registered():
            try:
                provider = ConversationProviderFactory.create(provider_name)
                report[provider_name] = provider.capabilities()
            except AIProviderError:
                continue
        return report

    def providers(self) -> tuple[ProviderName, ...]:
        """Return every provider name currently registered."""
        return tuple(ConversationProviderRegistry.all_registered().keys())

    @staticmethod
    def _build_config(request: RuntimeRequest) -> ConversationProviderConfig:
        return ConversationProviderConfig(
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
