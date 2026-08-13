from app.services.ai.conversation.base_provider import ConversationProvider
from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.provider_registry import GenericProviderRegistry


class ConversationProviderRegistry(GenericProviderRegistry[ProviderName, type[ConversationProvider]]):
    """Maps ProviderName to a concrete ConversationProvider class.

    Empty by default - a future provider module registers itself once,
    typically at import time:

        ConversationProviderRegistry.register(ProviderName.OPENAI, OpenAIConversationProvider)

    This file never needs to change to add a new provider; that's the
    entire point of a registry over a hardcoded mapping.

    Built on GenericProviderRegistry (app.services.ai.shared.provider_registry)
    rather than hand-rolling its own dict/lock/register/unregister/clear/get/
    is_registered/all_registered - register() still rejects re-registering an
    already-registered provider name unless overwrite=True, and every method
    is still guarded by a class-level, re-entrant, per-registry lock; both
    behaviors now live in the shared base instead of being duplicated here.
    _registration_error=AIProviderError keeps the exact exception type this
    registry always raised on a duplicate registration.
    """

    _registration_error = AIProviderError
