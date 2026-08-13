import asyncio
import pathlib

import pytest

import app.services.ai.runtime as runtime_package
from app.services.ai.conversation.base_provider import ConversationProvider
from app.services.ai.conversation.registry import ConversationProviderRegistry
from app.services.ai.conversation.types import ConversationStreamChunk
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.runtime.execution import RuntimeExecutor
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse
from app.services.ai.shared.provider_config import ConversationProviderConfig
from app.services.ai.shared.types import ProviderCapabilities
from app.services.prompt_builder.types import PromptPackage


class _FakeProvider(ConversationProvider):
    def __init__(self, config=None, *, chunks=None, healthy=True, caps=None):
        self.config = config or ConversationProviderConfig()
        self.chunks = chunks or []
        self.healthy = healthy
        self.caps = caps or ProviderCapabilities()

    def generate(self, prompt_package):
        raise NotImplementedError

    def health_check(self) -> bool:
        return self.healthy

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return "fake"

    def capabilities(self) -> ProviderCapabilities:
        return self.caps

    async def stream(self, prompt_package):
        for chunk in self.chunks:
            yield chunk


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(ConversationProviderRegistry._providers)
    ConversationProviderRegistry._providers.clear()
    yield
    ConversationProviderRegistry._providers.clear()
    ConversationProviderRegistry._providers.update(original)


def _request(**overrides):
    defaults = dict(
        organization_id=1,
        prompt_package=PromptPackage(system_prompt="s"),
        provider=ProviderName.OPENAI,
    )
    defaults.update(overrides)
    return RuntimeRequest(**defaults)


# --- construction / execute delegation --------------------------------------------------


def test_default_construction_builds_a_runtime_executor():
    runtime = AIRuntime()

    assert isinstance(runtime.executor, RuntimeExecutor)


def test_two_default_runtimes_do_not_share_an_executor():
    assert AIRuntime().executor is not AIRuntime().executor


def test_execute_delegates_to_the_injected_executor():
    class _StubExecutor:
        def __init__(self):
            self.called_with = None

        def execute(self, request):
            self.called_with = request
            return RuntimeResponse(success=True)

    executor = _StubExecutor()
    runtime = AIRuntime(executor=executor)
    request = _request()

    response = runtime.execute(request)

    assert executor.called_with is request
    assert response.success is True


def test_execute_never_raises_for_an_unregistered_provider():
    runtime = AIRuntime()

    response = runtime.execute(_request())

    assert response.success is False


# --- execute_stream -----------------------------------------------------------------------


def test_execute_stream_yields_provider_chunks_in_order():
    chunk1 = ConversationStreamChunk(delta="Hel", provider=ProviderName.OPENAI, model="fake")
    chunk2 = ConversationStreamChunk(delta="lo", provider=ProviderName.OPENAI, model="fake")
    provider = _FakeProvider(chunks=[chunk1, chunk2])
    ConversationProviderRegistry.register(ProviderName.OPENAI, lambda config: provider)
    runtime = AIRuntime()

    async def _collect():
        return [chunk async for chunk in runtime.execute_stream(_request())]

    chunks = asyncio.run(_collect())

    assert chunks == [chunk1, chunk2]


def test_execute_stream_stops_yielding_once_cancelled():
    chunk1 = ConversationStreamChunk(delta="a", provider=ProviderName.OPENAI, model="fake")
    chunk2 = ConversationStreamChunk(delta="b", provider=ProviderName.OPENAI, model="fake")
    provider = _FakeProvider(chunks=[chunk1, chunk2])
    ConversationProviderRegistry.register(ProviderName.OPENAI, lambda config: provider)
    runtime = AIRuntime()
    token = CancellationToken()

    async def _run():
        agen = runtime.execute_stream(_request(cancellation_token=token))
        first = await agen.__anext__()
        token.cancel()
        with pytest.raises(StopAsyncIteration):
            await agen.__anext__()
        return first

    result = asyncio.run(_run())

    assert result == chunk1


def test_execute_stream_propagates_a_provider_resolution_failure():
    runtime = AIRuntime()

    async def _collect():
        return [chunk async for chunk in runtime.execute_stream(_request())]

    with pytest.raises(Exception):  # AIProviderError - unregistered provider
        asyncio.run(_collect())


# --- providers / health / capabilities -----------------------------------------------------


def test_providers_returns_registered_provider_names():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    assert AIRuntime().providers() == (ProviderName.OPENAI,)


def test_providers_is_empty_when_nothing_is_registered():
    assert AIRuntime().providers() == ()


def test_health_reports_true_for_a_healthy_provider():
    ConversationProviderRegistry.register(ProviderName.OPENAI, lambda config: _FakeProvider(config, healthy=True))

    assert AIRuntime().health() == {ProviderName.OPENAI: True}


def test_health_reports_false_for_an_unhealthy_provider():
    ConversationProviderRegistry.register(ProviderName.OPENAI, lambda config: _FakeProvider(config, healthy=False))

    assert AIRuntime().health() == {ProviderName.OPENAI: False}


def test_health_reports_false_when_construction_raises_rather_than_propagating():
    def _boom(config):
        raise ValueError("cannot construct")

    ConversationProviderRegistry.register(ProviderName.OPENAI, _boom)

    assert AIRuntime().health() == {ProviderName.OPENAI: False}


def test_capabilities_reports_each_registered_providers_declared_capabilities():
    caps = ProviderCapabilities(supports_streaming=True)
    ConversationProviderRegistry.register(ProviderName.OPENAI, lambda config: _FakeProvider(config, caps=caps))

    assert AIRuntime().capabilities() == {ProviderName.OPENAI: caps}


def test_capabilities_is_empty_when_nothing_is_registered():
    assert AIRuntime().capabilities() == {}


# --- no provider knowledge --------------------------------------------------------------


def test_runtime_package_never_references_a_specific_vendor_by_name():
    vendor_tokens = (
        "openai",
        "anthropic",
        "gemini",
        "ollama",
        "openrouter",
        "deepseek",
        "qwen",
        "mistral",
        "grok",
    )
    package_dir = pathlib.Path(runtime_package.__file__).parent
    for path in package_dir.glob("*.py"):
        text = path.read_text().lower()
        for token in vendor_tokens:
            assert token not in text, f"{path.name} references vendor token '{token}'"
