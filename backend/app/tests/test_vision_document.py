import pytest

from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.provider_config import BaseProviderConfig
from app.services.ai.vision.document.base_provider import DocumentVisionProvider
from app.services.ai.vision.document.provider_factory import DocumentVisionProviderFactory
from app.services.ai.vision.document.registry import DocumentVisionProviderRegistry
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.request import VisionInput, VisionInputKind, VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.base_provider import BaseVisionProvider
from app.services.ai.vision.shared.exceptions import VisionProviderError

_ALL_MEMBERS = ("understand", "health_check", "provider_name", "model_name")


def _stub(name):
    return {
        "understand": lambda self, request: VisionResponse(success=True),
        "health_check": lambda self: True,
        "provider_name": property(lambda self: ProviderName.OPENAI),
        "model_name": property(lambda self: "fake"),
    }[name]


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(DocumentVisionProviderRegistry._providers)
    DocumentVisionProviderRegistry._providers.clear()
    yield
    DocumentVisionProviderRegistry._providers.clear()
    DocumentVisionProviderRegistry._providers.update(original)


def _request():
    return VisionRequest(
        inputs=(VisionInput(kind=VisionInputKind.DOCUMENT, path="/tmp/x.pdf"),), capability_category="document"
    )


def test_document_vision_provider_is_a_base_vision_provider():
    assert issubclass(DocumentVisionProvider, BaseVisionProvider)


def test_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        DocumentVisionProvider()


@pytest.mark.parametrize("missing_member", _ALL_MEMBERS)
def test_a_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    namespace = {name: _stub(name) for name in _ALL_MEMBERS if name != missing_member}
    incomplete = type("IncompleteProvider", (DocumentVisionProvider,), namespace)

    with pytest.raises(TypeError):
        incomplete()


class _FakeDocumentProvider(DocumentVisionProvider):
    def __init__(self, config=None):
        self.config = config

    def understand(self, request: VisionRequest) -> VisionResponse:
        return VisionResponse(success=True, confidence=0.8)

    def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return "fake-doc-vision"


def test_a_complete_subclass_can_be_instantiated_and_used():
    provider = _FakeDocumentProvider()

    response = provider.understand(_request())

    assert response.success is True


def test_registry_starts_empty():
    assert DocumentVisionProviderRegistry.get(ProviderName.OPENAI) is None


def test_register_and_get():
    DocumentVisionProviderRegistry.register(ProviderName.OPENAI, _FakeDocumentProvider)

    assert DocumentVisionProviderRegistry.get(ProviderName.OPENAI) is _FakeDocumentProvider


def test_registering_a_duplicate_raises_vision_provider_error():
    DocumentVisionProviderRegistry.register(ProviderName.OPENAI, _FakeDocumentProvider)

    with pytest.raises(VisionProviderError, match="already registered"):
        DocumentVisionProviderRegistry.register(ProviderName.OPENAI, _FakeDocumentProvider)


def test_overwrite_true_replaces_the_previous_registration():
    class _OtherProvider(_FakeDocumentProvider):
        pass

    DocumentVisionProviderRegistry.register(ProviderName.OPENAI, _FakeDocumentProvider)
    DocumentVisionProviderRegistry.register(ProviderName.OPENAI, _OtherProvider, overwrite=True)

    assert DocumentVisionProviderRegistry.get(ProviderName.OPENAI) is _OtherProvider


def test_unregister_removes_a_registration():
    DocumentVisionProviderRegistry.register(ProviderName.OPENAI, _FakeDocumentProvider)

    DocumentVisionProviderRegistry.unregister(ProviderName.OPENAI)

    assert DocumentVisionProviderRegistry.get(ProviderName.OPENAI) is None


def test_factory_raises_ai_provider_error_when_unregistered():
    with pytest.raises(AIProviderError, match="Unsupported document_vision provider"):
        DocumentVisionProviderFactory.create(ProviderName.OPENAI)


def test_factory_constructs_the_registered_provider():
    DocumentVisionProviderRegistry.register(ProviderName.OPENAI, _FakeDocumentProvider)

    provider = DocumentVisionProviderFactory.create(ProviderName.OPENAI)

    assert isinstance(provider, _FakeDocumentProvider)


def test_factory_constructs_with_a_default_config_when_none_given():
    DocumentVisionProviderRegistry.register(ProviderName.OPENAI, _FakeDocumentProvider)

    provider = DocumentVisionProviderFactory.create(ProviderName.OPENAI)

    assert isinstance(provider.config, BaseProviderConfig)


def test_adding_a_new_provider_requires_no_factory_modification():
    class _AnotherProvider(_FakeDocumentProvider):
        pass

    DocumentVisionProviderRegistry.register(ProviderName.ANTHROPIC, _AnotherProvider)

    provider = DocumentVisionProviderFactory.create(ProviderName.ANTHROPIC)

    assert isinstance(provider, _AnotherProvider)
