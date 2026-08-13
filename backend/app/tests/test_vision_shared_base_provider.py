import pytest

from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.shared.base_provider import BaseVisionProvider
from app.services.ai.vision.shared.types import VisionCapabilities

_ALL_MEMBERS = ("health_check", "provider_name", "model_name")


def _stub(name):
    return {
        "health_check": lambda self: True,
        "provider_name": property(lambda self: ProviderName.OPENAI),
        "model_name": property(lambda self: "fake-model"),
    }[name]


def test_base_vision_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseVisionProvider()


@pytest.mark.parametrize("missing_member", _ALL_MEMBERS)
def test_a_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    namespace = {name: _stub(name) for name in _ALL_MEMBERS if name != missing_member}
    incomplete = type("IncompleteProvider", (BaseVisionProvider,), namespace)

    with pytest.raises(TypeError):
        incomplete()


class _FakeProvider(BaseVisionProvider):
    def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return "fake-model"


def test_a_complete_subclass_can_be_instantiated():
    assert isinstance(_FakeProvider(), BaseVisionProvider)


def test_initialize_and_shutdown_default_to_no_ops():
    provider = _FakeProvider()

    assert provider.initialize() is None
    assert provider.shutdown() is None


def test_capabilities_defaults_to_nothing_declared():
    capabilities = _FakeProvider().capabilities()

    assert isinstance(capabilities, VisionCapabilities)
    assert capabilities.declared == frozenset()


def test_metadata_defaults_to_a_minimal_provider_metadata():
    from app.services.ai.shared.provider_metadata import ProviderMetadata

    metadata = _FakeProvider().metadata()

    assert isinstance(metadata, ProviderMetadata)
    assert metadata.provider_name == "openai"


def test_contract_version_defaults_to_one_point_zero():
    assert _FakeProvider.contract_version == "1.0"
