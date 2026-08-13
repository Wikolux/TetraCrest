import pytest

from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.provider_config import BaseProviderConfig
from app.services.ai.vision.analysis.base_provider import AnalysisProvider
from app.services.ai.vision.analysis.provider_factory import AnalysisProviderFactory
from app.services.ai.vision.analysis.registry import AnalysisProviderRegistry
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.request import VisionInput, VisionInputKind, VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.base_provider import BaseVisionProvider
from app.services.ai.vision.shared.exceptions import VisionProviderError
from app.services.ai.vision.shared.types import DetectedObject

_ALL_MEMBERS = ("analyze", "health_check", "provider_name", "model_name")


def _stub(name):
    return {
        "analyze": lambda self, request: VisionResponse(success=True),
        "health_check": lambda self: True,
        "provider_name": property(lambda self: ProviderName.OPENAI),
        "model_name": property(lambda self: "fake"),
    }[name]


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(AnalysisProviderRegistry._providers)
    AnalysisProviderRegistry._providers.clear()
    yield
    AnalysisProviderRegistry._providers.clear()
    AnalysisProviderRegistry._providers.update(original)


def _request():
    return VisionRequest(
        inputs=(VisionInput(kind=VisionInputKind.IMAGE, bytes_data=b"x"),), capability_category="analysis"
    )


def test_analysis_provider_is_a_base_vision_provider():
    assert issubclass(AnalysisProvider, BaseVisionProvider)


def test_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        AnalysisProvider()


@pytest.mark.parametrize("missing_member", _ALL_MEMBERS)
def test_a_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    namespace = {name: _stub(name) for name in _ALL_MEMBERS if name != missing_member}
    incomplete = type("IncompleteProvider", (AnalysisProvider,), namespace)

    with pytest.raises(TypeError):
        incomplete()


class _FakeAnalysisProvider(AnalysisProvider):
    def __init__(self, config=None):
        self.config = config

    def analyze(self, request: VisionRequest) -> VisionResponse:
        return VisionResponse(success=True, objects=(DetectedObject(label="box"),))

    def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return "fake-analysis"


def test_a_complete_subclass_can_be_instantiated_and_used():
    provider = _FakeAnalysisProvider()

    response = provider.analyze(_request())

    assert response.objects[0].label == "box"


def test_registry_starts_empty():
    assert AnalysisProviderRegistry.get(ProviderName.OPENAI) is None


def test_register_and_get():
    AnalysisProviderRegistry.register(ProviderName.OPENAI, _FakeAnalysisProvider)

    assert AnalysisProviderRegistry.get(ProviderName.OPENAI) is _FakeAnalysisProvider


def test_registering_a_duplicate_raises_vision_provider_error():
    AnalysisProviderRegistry.register(ProviderName.OPENAI, _FakeAnalysisProvider)

    with pytest.raises(VisionProviderError, match="already registered"):
        AnalysisProviderRegistry.register(ProviderName.OPENAI, _FakeAnalysisProvider)


def test_overwrite_true_replaces_the_previous_registration():
    class _OtherProvider(_FakeAnalysisProvider):
        pass

    AnalysisProviderRegistry.register(ProviderName.OPENAI, _FakeAnalysisProvider)
    AnalysisProviderRegistry.register(ProviderName.OPENAI, _OtherProvider, overwrite=True)

    assert AnalysisProviderRegistry.get(ProviderName.OPENAI) is _OtherProvider


def test_unregister_removes_a_registration():
    AnalysisProviderRegistry.register(ProviderName.OPENAI, _FakeAnalysisProvider)

    AnalysisProviderRegistry.unregister(ProviderName.OPENAI)

    assert AnalysisProviderRegistry.get(ProviderName.OPENAI) is None


def test_factory_raises_ai_provider_error_when_unregistered():
    with pytest.raises(AIProviderError, match="Unsupported analysis_vision provider"):
        AnalysisProviderFactory.create(ProviderName.OPENAI)


def test_factory_constructs_the_registered_provider():
    AnalysisProviderRegistry.register(ProviderName.OPENAI, _FakeAnalysisProvider)

    provider = AnalysisProviderFactory.create(ProviderName.OPENAI)

    assert isinstance(provider, _FakeAnalysisProvider)


def test_factory_constructs_with_a_default_config_when_none_given():
    AnalysisProviderRegistry.register(ProviderName.OPENAI, _FakeAnalysisProvider)

    provider = AnalysisProviderFactory.create(ProviderName.OPENAI)

    assert isinstance(provider.config, BaseProviderConfig)


def test_adding_a_new_provider_requires_no_factory_modification():
    class _AnotherProvider(_FakeAnalysisProvider):
        pass

    AnalysisProviderRegistry.register(ProviderName.ANTHROPIC, _AnotherProvider)

    provider = AnalysisProviderFactory.create(ProviderName.ANTHROPIC)

    assert isinstance(provider, _AnotherProvider)
