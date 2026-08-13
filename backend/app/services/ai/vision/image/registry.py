"""ImageVisionProviderRegistry - maps ProviderName to a concrete
ImageVisionProvider class. Built on GenericProviderRegistry
(app.services.ai.shared.provider_registry) rather than hand-copying
ConversationProviderRegistry's shape an eighth time.

Empty by default - no image vision provider exists yet (architecture
only). A future provider registers itself, typically at import time:

    ImageVisionProviderRegistry.register(ProviderName.OPENAI, OpenAIImageVisionProvider)

This file never needs to change to add a new provider (Open/Closed).
"""

from app.services.ai.shared.provider_registry import GenericProviderRegistry
from app.services.ai.vision.image.base_provider import ImageVisionProvider
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.shared.exceptions import VisionProviderError


class ImageVisionProviderRegistry(GenericProviderRegistry[ProviderName, type[ImageVisionProvider]]):
    _registration_error = VisionProviderError
