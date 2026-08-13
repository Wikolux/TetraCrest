"""ImageVisionProviderFactory - resolves a ProviderName into a concrete
ImageVisionProvider via ImageVisionProviderRegistry. Mirrors
ConversationProviderFactory exactly, reusing BaseProviderFactory
(app.services.ai.shared.base_factory) rather than duplicating its
"resolve or fail clearly" logic.

Providers are constructed from BaseProviderConfig
(app.services.ai.shared.provider_config) - the same generic
connection/auth/observability config every provider-shaped factory in
this platform uses - reused as-is rather than inventing a vision-specific
config with no genuinely new fields to justify one.
"""

from app.services.ai.shared.base_factory import BaseProviderFactory
from app.services.ai.shared.provider_config import BaseProviderConfig
from app.services.ai.vision.image.base_provider import ImageVisionProvider
from app.services.ai.vision.image.registry import ImageVisionProviderRegistry
from app.services.ai.vision.providers.enums import ProviderName


class ImageVisionProviderFactory(BaseProviderFactory[ImageVisionProvider, BaseProviderConfig]):
    @staticmethod
    def create(provider_name: ProviderName, config: BaseProviderConfig | None = None) -> ImageVisionProvider:
        provider_class = ImageVisionProviderRegistry.get(provider_name)
        return BaseProviderFactory.build(provider_class, provider_name, config or BaseProviderConfig(), "image_vision")
