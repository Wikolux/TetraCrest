import pytest

from app.services.ai.vision.analysis.base_provider import AnalysisProvider
from app.services.ai.vision.analysis.registry import AnalysisProviderRegistry
from app.services.ai.vision.document.base_provider import DocumentVisionProvider
from app.services.ai.vision.document.registry import DocumentVisionProviderRegistry
from app.services.ai.vision.execution import VisionExecutor
from app.services.ai.vision.extraction.base_provider import ExtractionProvider
from app.services.ai.vision.extraction.registry import ExtractionProviderRegistry
from app.services.ai.vision.image.base_provider import ImageVisionProvider
from app.services.ai.vision.image.registry import ImageVisionProviderRegistry
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.request import VisionInput, VisionInputKind, VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.runtime import VisionRuntime
from app.services.ai.vision.shared.types import VisionCapabilities


_REGISTRIES = {
    "image": ImageVisionProviderRegistry,
    "document": DocumentVisionProviderRegistry,
    "extraction": ExtractionProviderRegistry,
    "analysis": AnalysisProviderRegistry,
}


@pytest.fixture(autouse=True)
def _isolated_registries():
    originals = {name: dict(registry._providers) for name, registry in _REGISTRIES.items()}
    for registry in _REGISTRIES.values():
        registry._providers.clear()
    yield
    for name, registry in _REGISTRIES.items():
        registry._providers.clear()
        registry._providers.update(originals[name])


class _FakeImageProvider(ImageVisionProvider):
    def __init__(self, config=None, *, healthy=True, capabilities=None):
        self.config = config
        self._healthy = healthy
        self._capabilities = capabilities or VisionCapabilities()

    def describe(self, request):
        return VisionResponse(success=True)

    def health_check(self):
        return self._healthy

    def capabilities(self):
        return self._capabilities

    @property
    def provider_name(self):
        return ProviderName.OPENAI

    @property
    def model_name(self):
        return "fake-image"


class _FakeDocumentProvider(DocumentVisionProvider):
    def __init__(self, config=None):
        self.config = config

    def understand(self, request):
        return VisionResponse(success=True)

    def health_check(self):
        return True

    @property
    def provider_name(self):
        return ProviderName.ANTHROPIC

    @property
    def model_name(self):
        return "fake-document"


class _FakeExtractionProvider(ExtractionProvider):
    def __init__(self, config=None):
        self.config = config

    def extract(self, request):
        return VisionResponse(success=True)

    def health_check(self):
        return True

    @property
    def provider_name(self):
        return ProviderName.OPENAI

    @property
    def model_name(self):
        return "fake-extraction"


class _FakeAnalysisProvider(AnalysisProvider):
    def __init__(self, config=None):
        self.config = config

    def analyze(self, request):
        return VisionResponse(success=True)

    def health_check(self):
        return True

    @property
    def provider_name(self):
        return ProviderName.OPENAI

    @property
    def model_name(self):
        return "fake-analysis"


class _BrokenProvider(ImageVisionProvider):
    def __init__(self, config=None):
        pass

    def describe(self, request):
        return VisionResponse(success=True)

    def health_check(self):
        raise RuntimeError("provider is on fire")

    def capabilities(self):
        raise RuntimeError("provider is on fire")

    @property
    def provider_name(self):
        return ProviderName.OPENAI

    @property
    def model_name(self):
        return "broken"


def _request(capability_category="image", provider=ProviderName.OPENAI):
    return VisionRequest(
        inputs=(VisionInput(kind=VisionInputKind.IMAGE, bytes_data=b"x"),),
        capability_category=capability_category,
        provider=provider,
    )


# --- execute() delegation --------------------------------------------------------------------


def test_execute_delegates_to_the_executor():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)
    runtime = VisionRuntime()

    response = runtime.execute(_request())

    assert response.success is True


def test_default_construction_builds_its_own_executor():
    runtime = VisionRuntime()

    assert isinstance(runtime.executor, VisionExecutor)


def test_an_injected_executor_is_used_directly_instead_of_building_one():
    executor = VisionExecutor()

    runtime = VisionRuntime(executor=executor)

    assert runtime.executor is executor


def test_two_runtimes_built_with_defaults_do_not_share_an_executor():
    runtime_a = VisionRuntime()
    runtime_b = VisionRuntime()

    assert runtime_a.executor is not runtime_b.executor


def test_max_retries_is_forwarded_to_the_default_executor():
    runtime = VisionRuntime(max_retries=3)

    assert runtime.executor.max_retries == 3


def test_execute_reflects_a_provider_level_failure_without_raising():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _BrokenProvider)
    runtime = VisionRuntime()

    response = runtime.execute(_request())

    assert response.success is True  # describe() itself succeeds; only health_check is broken


# --- health() ----------------------------------------------------------------------------------


def test_health_is_empty_when_nothing_is_registered():
    runtime = VisionRuntime()

    assert runtime.health() == {}


def test_health_reports_a_healthy_registered_provider():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)
    runtime = VisionRuntime()

    report = runtime.health()

    assert report[("image", ProviderName.OPENAI)] is True


def test_health_reports_unhealthy_without_raising_when_health_check_returns_false():
    ImageVisionProviderRegistry.register(
        ProviderName.OPENAI, lambda config=None: _FakeImageProvider(config, healthy=False)
    )
    runtime = VisionRuntime()

    report = runtime.health()

    assert report[("image", ProviderName.OPENAI)] is False


def test_health_reports_unhealthy_without_raising_when_health_check_raises():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _BrokenProvider)
    runtime = VisionRuntime()

    report = runtime.health()

    assert report[("image", ProviderName.OPENAI)] is False


def test_health_aggregates_across_every_capability():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)
    DocumentVisionProviderRegistry.register(ProviderName.ANTHROPIC, _FakeDocumentProvider)
    ExtractionProviderRegistry.register(ProviderName.OPENAI, _FakeExtractionProvider)
    AnalysisProviderRegistry.register(ProviderName.OPENAI, _FakeAnalysisProvider)
    runtime = VisionRuntime()

    report = runtime.health()

    assert report[("image", ProviderName.OPENAI)] is True
    assert report[("document", ProviderName.ANTHROPIC)] is True
    assert report[("extraction", ProviderName.OPENAI)] is True
    assert report[("analysis", ProviderName.OPENAI)] is True


# --- capabilities() ------------------------------------------------------------------------------


def test_capabilities_is_empty_when_nothing_is_registered():
    runtime = VisionRuntime()

    assert runtime.capabilities() == {}


def test_capabilities_reports_the_registered_providers_capabilities():
    caps = VisionCapabilities(("describe", "caption"))
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, lambda config=None: _FakeImageProvider(config, capabilities=caps))
    runtime = VisionRuntime()

    report = runtime.capabilities()

    assert report[("image", ProviderName.OPENAI)] is caps


def test_capabilities_skips_a_broken_provider_without_raising():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _BrokenProvider)
    runtime = VisionRuntime()

    report = runtime.capabilities()

    assert ("image", ProviderName.OPENAI) not in report


# --- providers() ---------------------------------------------------------------------------------


def test_providers_is_empty_for_every_capability_when_nothing_is_registered():
    runtime = VisionRuntime()

    report = runtime.providers()

    assert report == {"image": (), "document": (), "extraction": (), "analysis": ()}


def test_providers_lists_every_registered_provider_per_capability():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)
    DocumentVisionProviderRegistry.register(ProviderName.ANTHROPIC, _FakeDocumentProvider)
    runtime = VisionRuntime()

    report = runtime.providers()

    assert ProviderName.OPENAI in report["image"]
    assert ProviderName.ANTHROPIC in report["document"]
    assert report["extraction"] == ()
    assert report["analysis"] == ()


def test_providers_does_not_leak_registrations_across_capabilities():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)
    runtime = VisionRuntime()

    report = runtime.providers()

    assert report["document"] == ()
    assert report["extraction"] == ()
    assert report["analysis"] == ()
