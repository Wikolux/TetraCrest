import pytest

from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.provider_config import BaseProviderConfig
from app.services.ai.vision.image.base_provider import ImageVisionProvider
from app.services.ai.vision.image.provider_factory import ImageVisionProviderFactory
from app.services.ai.vision.image.registry import ImageVisionProviderRegistry
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.request import VisionInput, VisionInputKind, VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.base_provider import BaseVisionProvider
from app.services.ai.vision.shared.exceptions import VisionProviderError

_ALL_MEMBERS = ("describe", "health_check", "provider_name", "model_name")


def _stub(name):
    return {
        "describe": lambda self, request: VisionResponse(success=True),
        "health_check": lambda self: True,
        "provider_name": property(lambda self: ProviderName.OPENAI),
        "model_name": property(lambda self: "fake"),
    }[name]


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(ImageVisionProviderRegistry._providers)
    ImageVisionProviderRegistry._providers.clear()
    yield
    ImageVisionProviderRegistry._providers.clear()
    ImageVisionProviderRegistry._providers.update(original)


def _request():
    return VisionRequest(
        inputs=(VisionInput(kind=VisionInputKind.IMAGE, bytes_data=b"x"),), capability_category="image"
    )


# --- ABC enforcement -------------------------------------------------------------------


def test_image_vision_provider_is_a_base_vision_provider():
    assert issubclass(ImageVisionProvider, BaseVisionProvider)


def test_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ImageVisionProvider()


@pytest.mark.parametrize("missing_member", _ALL_MEMBERS)
def test_a_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    namespace = {name: _stub(name) for name in _ALL_MEMBERS if name != missing_member}
    incomplete = type("IncompleteProvider", (ImageVisionProvider,), namespace)

    with pytest.raises(TypeError):
        incomplete()


class _FakeImageProvider(ImageVisionProvider):
    def __init__(self, config=None):
        self.config = config

    def describe(self, request: VisionRequest) -> VisionResponse:
        return VisionResponse(success=True, confidence=0.9)

    def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return "fake-vision"


def test_a_complete_subclass_can_be_instantiated_and_used():
    provider = _FakeImageProvider()

    response = provider.describe(_request())

    assert response.success is True
    assert response.confidence == 0.9


# --- registry ---------------------------------------------------------------------------


def test_registry_starts_empty():
    assert ImageVisionProviderRegistry.get(ProviderName.OPENAI) is None


def test_register_and_get():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)

    assert ImageVisionProviderRegistry.get(ProviderName.OPENAI) is _FakeImageProvider
    assert ImageVisionProviderRegistry.is_registered(ProviderName.OPENAI) is True


def test_registering_a_duplicate_raises_vision_provider_error():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)

    with pytest.raises(VisionProviderError, match="already registered"):
        ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)


def test_overwrite_true_replaces_the_previous_registration():
    class _OtherProvider(_FakeImageProvider):
        pass

    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)

    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _OtherProvider, overwrite=True)

    assert ImageVisionProviderRegistry.get(ProviderName.OPENAI) is _OtherProvider


def test_unregister_removes_a_registration():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)

    ImageVisionProviderRegistry.unregister(ProviderName.OPENAI)

    assert ImageVisionProviderRegistry.get(ProviderName.OPENAI) is None


def test_clear_removes_every_registration():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)

    ImageVisionProviderRegistry.clear()

    assert ImageVisionProviderRegistry.all_registered() == {}


def test_never_shares_storage_with_a_different_capabilitys_registry():
    from app.services.ai.vision.document.registry import DocumentVisionProviderRegistry

    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)

    assert DocumentVisionProviderRegistry.get(ProviderName.OPENAI) is None


# --- factory ------------------------------------------------------------------------------


def test_factory_raises_ai_provider_error_when_unregistered():
    with pytest.raises(AIProviderError, match="Unsupported image_vision provider"):
        ImageVisionProviderFactory.create(ProviderName.OPENAI)


def test_factory_constructs_the_registered_provider():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)

    provider = ImageVisionProviderFactory.create(ProviderName.OPENAI)

    assert isinstance(provider, _FakeImageProvider)
    assert isinstance(provider, ImageVisionProvider)


def test_factory_constructs_with_a_default_config_when_none_given():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)

    provider = ImageVisionProviderFactory.create(ProviderName.OPENAI)

    assert isinstance(provider.config, BaseProviderConfig)


def test_factory_passes_through_an_explicit_config():
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _FakeImageProvider)
    config = BaseProviderConfig(api_key="secret")

    provider = ImageVisionProviderFactory.create(ProviderName.OPENAI, config)

    assert provider.config is config


def test_adding_a_new_provider_requires_no_factory_modification():
    class _AnotherProvider(_FakeImageProvider):
        pass

    ImageVisionProviderRegistry.register(ProviderName.ANTHROPIC, _AnotherProvider)

    provider = ImageVisionProviderFactory.create(ProviderName.ANTHROPIC)

    assert isinstance(provider, _AnotherProvider)
