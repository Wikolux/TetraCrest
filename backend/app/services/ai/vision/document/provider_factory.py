from app.services.ai.shared.base_factory import BaseProviderFactory
from app.services.ai.shared.provider_config import BaseProviderConfig
from app.services.ai.vision.document.base_provider import DocumentVisionProvider
from app.services.ai.vision.document.registry import DocumentVisionProviderRegistry
from app.services.ai.vision.providers.enums import ProviderName


class DocumentVisionProviderFactory(BaseProviderFactory[DocumentVisionProvider, BaseProviderConfig]):
    @staticmethod
    def create(provider_name: ProviderName, config: BaseProviderConfig | None = None) -> DocumentVisionProvider:
        provider_class = DocumentVisionProviderRegistry.get(provider_name)
        return BaseProviderFactory.build(
            provider_class, provider_name, config or BaseProviderConfig(), "document_vision"
        )
