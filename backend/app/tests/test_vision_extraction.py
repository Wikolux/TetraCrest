import pytest

from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.provider_config import BaseProviderConfig
from app.services.ai.vision.extraction.base_provider import ExtractionProvider
from app.services.ai.vision.extraction.provider_factory import ExtractionProviderFactory
from app.services.ai.vision.extraction.registry import ExtractionProviderRegistry
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.request import VisionInput, VisionInputKind, VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.base_provider import BaseVisionProvider
from app.services.ai.vision.shared.exceptions import VisionProviderError
from app.services.ai.vision.shared.types import ExtractedText

_ALL_MEMBERS = ("extract", "health_check", "provider_name", "model_name")


def _stub(name):
    return {
        "extract": lambda self, request: VisionResponse(success=True),
        "health_check": lambda self: True,
        "provider_name": property(lambda self: ProviderName.OPENAI),
        "model_name": property(lambda self: "fake"),
    }[name]


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(ExtractionProviderRegistry._providers)
    ExtractionProviderRegistry._providers.clear()
    yield
    ExtractionProviderRegistry._providers.clear()
    ExtractionProviderRegistry._providers.update(original)


def _request():
    return VisionRequest(
        inputs=(VisionInput(kind=VisionInputKind.IMAGE, bytes_data=b"x"),), capability_category="extraction"
    )


def test_extraction_provider_is_a_base_vision_provider():
    assert issubclass(ExtractionProvider, BaseVisionProvider)


def test_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ExtractionProvider()


@pytest.mark.parametrize("missing_member", _ALL_MEMBERS)
def test_a_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    namespace = {name: _stub(name) for name in _ALL_MEMBERS if name != missing_member}
    incomplete = type("IncompleteProvider", (ExtractionProvider,), namespace)

    with pytest.raises(TypeError):
        incomplete()


class _FakeExtractionProvider(ExtractionProvider):
    def __init__(self, config=None):
        self.config = config

    def extract(self, request: VisionRequest) -> VisionResponse:
        return VisionResponse(success=True, extracted_text=(ExtractedText(content="hello"),))

    def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return "fake-extraction"


def test_a_complete_subclass_can_be_instantiated_and_used():
    provider = _FakeExtractionProvider()

    response = provider.extract(_request())

    assert response.extracted_text[0].content == "hello"


def test_registry_starts_empty():
    assert ExtractionProviderRegistry.get(ProviderName.OPENAI) is None


def test_register_and_get():
    ExtractionProviderRegistry.register(ProviderName.OPENAI, _FakeExtractionProvider)

    assert ExtractionProviderRegistry.get(ProviderName.OPENAI) is _FakeExtractionProvider


def test_registering_a_duplicate_raises_vision_provider_error():
    ExtractionProviderRegistry.register(ProviderName.OPENAI, _FakeExtractionProvider)

    with pytest.raises(VisionProviderError, match="already registered"):
        ExtractionProviderRegistry.register(ProviderName.OPENAI, _FakeExtractionProvider)


def test_overwrite_true_replaces_the_previous_registration():
    class _OtherProvider(_FakeExtractionProvider):
        pass

    ExtractionProviderRegistry.register(ProviderName.OPENAI, _FakeExtractionProvider)
    ExtractionProviderRegistry.register(ProviderName.OPENAI, _OtherProvider, overwrite=True)

    assert ExtractionProviderRegistry.get(ProviderName.OPENAI) is _OtherProvider


def test_unregister_removes_a_registration():
    ExtractionProviderRegistry.register(ProviderName.OPENAI, _FakeExtractionProvider)

    ExtractionProviderRegistry.unregister(ProviderName.OPENAI)

    assert ExtractionProviderRegistry.get(ProviderName.OPENAI) is None


def test_factory_raises_ai_provider_error_when_unregistered():
    with pytest.raises(AIProviderError, match="Unsupported extraction_vision provider"):
        ExtractionProviderFactory.create(ProviderName.OPENAI)


def test_factory_constructs_the_registered_provider():
    ExtractionProviderRegistry.register(ProviderName.OPENAI, _FakeExtractionProvider)

    provider = ExtractionProviderFactory.create(ProviderName.OPENAI)

    assert isinstance(provider, _FakeExtractionProvider)


def test_factory_constructs_with_a_default_config_when_none_given():
    ExtractionProviderRegistry.register(ProviderName.OPENAI, _FakeExtractionProvider)

    provider = ExtractionProviderFactory.create(ProviderName.OPENAI)

    assert isinstance(provider.config, BaseProviderConfig)


def test_adding_a_new_provider_requires_no_factory_modification():
    class _AnotherProvider(_FakeExtractionProvider):
        pass

    ExtractionProviderRegistry.register(ProviderName.ANTHROPIC, _AnotherProvider)

    provider = ExtractionProviderFactory.create(ProviderName.ANTHROPIC)

    assert isinstance(provider, _AnotherProvider)
