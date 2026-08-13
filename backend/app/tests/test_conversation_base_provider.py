import asyncio

import pytest

from app.services.ai.conversation.base_provider import ConversationProvider
from app.services.ai.conversation.types import ConversationResponse
from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.exceptions import StreamingError
from app.services.ai.shared.provider_metadata import ProviderMetadata
from app.services.ai.shared.response import AIResponseMetadata, FinishReason, ProviderResponse, UsageDetails
from app.services.ai.shared.types import ProviderCapabilities


class _CompleteFakeProvider(ConversationProvider):
    def generate(self, prompt_package) -> ConversationResponse:
        return ConversationResponse(
            text="fake response",
            response=ProviderResponse(
                metadata=AIResponseMetadata(
                    provider=ProviderName.OPENAI, model="fake-model", finish_reason=FinishReason.STOP
                ),
                usage=UsageDetails(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            ),
        )

    def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return "fake-model"


def test_conversation_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ConversationProvider()


def test_conforming_subclass_can_be_instantiated():
    provider = _CompleteFakeProvider()

    assert isinstance(provider, ConversationProvider)


def test_conforming_subclass_generate_returns_conversation_response():
    provider = _CompleteFakeProvider()

    response = provider.generate(prompt_package=object())

    assert isinstance(response, ConversationResponse)
    assert response.text == "fake response"


def test_conforming_subclass_exposes_provider_name_and_model_name():
    provider = _CompleteFakeProvider()

    assert provider.provider_name == ProviderName.OPENAI
    assert provider.model_name == "fake-model"


def test_conforming_subclass_health_check():
    assert _CompleteFakeProvider().health_check() is True


@pytest.mark.parametrize(
    "missing_member", ["generate", "health_check", "provider_name", "model_name"]
)
def test_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    members = {
        "generate": lambda self, prompt_package: None,
        "health_check": lambda self: True,
        "provider_name": property(lambda self: ProviderName.OPENAI),
        "model_name": property(lambda self: "fake-model"),
    }
    del members[missing_member]

    IncompleteProvider = type("IncompleteProvider", (ConversationProvider,), members)

    with pytest.raises(TypeError):
        IncompleteProvider()


# --- lifecycle hooks (Task 2): concrete defaults, no boilerplate required --------


def test_initialize_default_is_a_no_op():
    assert _CompleteFakeProvider().initialize() is None


def test_shutdown_default_is_a_no_op():
    assert _CompleteFakeProvider().shutdown() is None


def test_a_provider_not_overriding_lifecycle_hooks_is_still_instantiable():
    # confirms initialize/shutdown/capabilities/stream are NOT abstract -
    # a minimal provider implementing only the four original members
    # remains valid, preserving backward compatibility
    class _MinimalProvider(ConversationProvider):
        def generate(self, prompt_package):
            raise NotImplementedError

        def health_check(self) -> bool:
            return True

        @property
        def provider_name(self) -> ProviderName:
            return ProviderName.OPENAI

        @property
        def model_name(self) -> str:
            return "minimal"

    provider = _MinimalProvider()
    assert provider.initialize() is None
    assert provider.shutdown() is None
    assert provider.capabilities() == ProviderCapabilities()


# --- capability discovery (Task 4) ------------------------------------------------


def test_capabilities_default_declares_nothing_supported():
    capabilities = _CompleteFakeProvider().capabilities()

    assert capabilities == ProviderCapabilities()


def test_capabilities_can_be_overridden():
    class _StreamingProvider(_CompleteFakeProvider):
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(supports_streaming=True, max_context_tokens=128000)

    capabilities = _StreamingProvider().capabilities()

    assert capabilities.supports_streaming is True
    assert capabilities.max_context_tokens == 128000


# --- provider metadata (Task 9) -----------------------------------------------------


def test_metadata_default_uses_provider_name_only():
    metadata = _CompleteFakeProvider().metadata()

    assert isinstance(metadata, ProviderMetadata)
    assert metadata.provider_name == "openai"
    assert metadata.vendor is None


def test_metadata_can_be_overridden():
    class _DocumentedProvider(_CompleteFakeProvider):
        def metadata(self) -> ProviderMetadata:
            return ProviderMetadata(
                provider_name="openai", vendor="OpenAI", homepage="https://openai.com", supports_cloud=True
            )

    metadata = _DocumentedProvider().metadata()

    assert metadata.vendor == "OpenAI"
    assert metadata.homepage == "https://openai.com"


# --- contract versioning (Task 10) --------------------------------------------------


def test_contract_version_defaults_to_one_point_zero():
    assert ConversationProvider.contract_version == "1.0"
    assert _CompleteFakeProvider().contract_version == "1.0"


def test_contract_version_can_be_overridden_by_a_future_provider():
    class _V2Provider(_CompleteFakeProvider):
        contract_version = "2.0"

    assert _V2Provider().contract_version == "2.0"
    # overriding v2 must never affect the base contract or existing v1 providers
    assert ConversationProvider.contract_version == "1.0"
    assert _CompleteFakeProvider().contract_version == "1.0"


# --- streaming (Task 3) ------------------------------------------------------------


def test_default_stream_raises_streaming_error():
    provider = _CompleteFakeProvider()

    async def _consume():
        async for _ in provider.stream(prompt_package=object()):
            pass  # pragma: no cover - default never yields

    with pytest.raises(StreamingError, match="does not support streaming"):
        asyncio.run(_consume())


def test_stream_can_be_overridden_with_a_real_async_generator():
    class _StreamingProvider(_CompleteFakeProvider):
        async def stream(self, prompt_package):
            for piece in ["Hel", "lo"]:
                yield piece

    async def _collect():
        return [chunk async for chunk in _StreamingProvider().stream(prompt_package=object())]

    chunks = asyncio.run(_collect())

    assert chunks == ["Hel", "lo"]


def test_stream_returns_an_async_generator_not_a_coroutine():
    import inspect

    provider = _CompleteFakeProvider()

    result = provider.stream(prompt_package=object())

    assert inspect.isasyncgen(result)
