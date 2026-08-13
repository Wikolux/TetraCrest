import pytest

from app.services.ai.conversation.base_provider import ConversationProvider
from app.services.ai.conversation.registry import ConversationProviderRegistry
from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.provider_registry import GenericProviderRegistry


def test_registry_is_built_on_the_generic_registry_not_a_parallel_type():
    assert issubclass(ConversationProviderRegistry, GenericProviderRegistry)


class _FakeProvider(ConversationProvider):
    def generate(self, prompt_package):
        raise NotImplementedError

    def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return "fake-model"


class _AnotherFakeProvider(ConversationProvider):
    def generate(self, prompt_package):
        raise NotImplementedError

    def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.ANTHROPIC

    @property
    def model_name(self) -> str:
        return "another-fake-model"


@pytest.fixture(autouse=True)
def _isolated_registry():
    """The registry is process-wide class state - snapshot and restore it
    around every test so tests never leak registrations into each other."""
    original = dict(ConversationProviderRegistry._providers)
    ConversationProviderRegistry._providers.clear()
    yield
    ConversationProviderRegistry._providers.clear()
    ConversationProviderRegistry._providers.update(original)


def test_registry_starts_empty_for_a_fresh_provider_name():
    assert ConversationProviderRegistry.get(ProviderName.OPENAI) is None


def test_register_and_get_a_provider():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    assert ConversationProviderRegistry.get(ProviderName.OPENAI) is _FakeProvider


def test_is_registered_reflects_registration_state():
    assert ConversationProviderRegistry.is_registered(ProviderName.OPENAI) is False

    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    assert ConversationProviderRegistry.is_registered(ProviderName.OPENAI) is True


def test_get_unregistered_provider_returns_none():
    assert ConversationProviderRegistry.get(ProviderName.GROK) is None


def test_registering_an_already_registered_provider_name_raises_by_default():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    with pytest.raises(AIProviderError, match="already registered"):
        ConversationProviderRegistry.register(ProviderName.OPENAI, _AnotherFakeProvider)

    # the original registration must survive a rejected duplicate attempt
    assert ConversationProviderRegistry.get(ProviderName.OPENAI) is _FakeProvider


def test_registering_with_overwrite_true_replaces_the_previous_registration():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)
    ConversationProviderRegistry.register(ProviderName.OPENAI, _AnotherFakeProvider, overwrite=True)

    assert ConversationProviderRegistry.get(ProviderName.OPENAI) is _AnotherFakeProvider


def test_registering_a_new_provider_name_never_requires_overwrite():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    assert ConversationProviderRegistry.get(ProviderName.OPENAI) is _FakeProvider


# --- unregister / clear (Task 8 hardening) --------------------------------------


def test_unregister_removes_a_registration():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    ConversationProviderRegistry.unregister(ProviderName.OPENAI)

    assert ConversationProviderRegistry.get(ProviderName.OPENAI) is None
    assert ConversationProviderRegistry.is_registered(ProviderName.OPENAI) is False


def test_unregister_an_unregistered_provider_does_not_raise():
    ConversationProviderRegistry.unregister(ProviderName.GROK)  # must not raise


def test_unregister_then_register_again_does_not_require_overwrite():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)
    ConversationProviderRegistry.unregister(ProviderName.OPENAI)

    ConversationProviderRegistry.register(ProviderName.OPENAI, _AnotherFakeProvider)  # must not raise

    assert ConversationProviderRegistry.get(ProviderName.OPENAI) is _AnotherFakeProvider


def test_clear_removes_every_registration():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)
    ConversationProviderRegistry.register(ProviderName.ANTHROPIC, _AnotherFakeProvider)

    ConversationProviderRegistry.clear()

    assert ConversationProviderRegistry.all_registered() == {}


def test_clear_on_an_already_empty_registry_does_not_raise():
    ConversationProviderRegistry.clear()  # must not raise


def test_multiple_providers_can_be_registered_independently():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)
    ConversationProviderRegistry.register(ProviderName.ANTHROPIC, _AnotherFakeProvider)

    assert ConversationProviderRegistry.get(ProviderName.OPENAI) is _FakeProvider
    assert ConversationProviderRegistry.get(ProviderName.ANTHROPIC) is _AnotherFakeProvider


def test_all_registered_reflects_current_registrations():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    assert ConversationProviderRegistry.all_registered() == {ProviderName.OPENAI: _FakeProvider}


def test_all_registered_returns_a_copy_not_a_live_view():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    snapshot = ConversationProviderRegistry.all_registered()
    snapshot[ProviderName.ANTHROPIC] = _AnotherFakeProvider

    assert ConversationProviderRegistry.get(ProviderName.ANTHROPIC) is None


def test_registry_accepts_a_brand_new_provider_without_any_registry_code_change():
    # simulates a future provider module registering itself - the
    # registry class itself needs no changes to support this
    class _FutureProvider(ConversationProvider):
        def generate(self, prompt_package):
            raise NotImplementedError

        def health_check(self) -> bool:
            return True

        @property
        def provider_name(self) -> ProviderName:
            return ProviderName.DEEPSEEK

        @property
        def model_name(self) -> str:
            return "future-model"

    ConversationProviderRegistry.register(ProviderName.DEEPSEEK, _FutureProvider)

    assert ConversationProviderRegistry.get(ProviderName.DEEPSEEK) is _FutureProvider
