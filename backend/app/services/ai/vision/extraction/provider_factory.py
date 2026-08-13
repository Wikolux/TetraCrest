from app.services.ai.shared.base_factory import BaseProviderFactory
from app.services.ai.shared.provider_config import BaseProviderConfig
from app.services.ai.vision.extraction.base_provider import ExtractionProvider
from app.services.ai.vision.extraction.registry import ExtractionProviderRegistry
from app.services.ai.vision.providers.enums import ProviderName


class ExtractionProviderFactory(BaseProviderFactory[ExtractionProvider, BaseProviderConfig]):
    @staticmethod
    def create(provider_name: ProviderName, config: BaseProviderConfig | None = None) -> ExtractionProvider:
        provider_class = ExtractionProviderRegistry.get(provider_name)
        return BaseProviderFactory.build(
            provider_class, provider_name, config or BaseProviderConfig(), "extraction_vision"
        )
