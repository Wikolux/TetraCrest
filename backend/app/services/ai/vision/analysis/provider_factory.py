from app.services.ai.shared.base_factory import BaseProviderFactory
from app.services.ai.shared.provider_config import BaseProviderConfig
from app.services.ai.vision.analysis.base_provider import AnalysisProvider
from app.services.ai.vision.analysis.registry import AnalysisProviderRegistry
from app.services.ai.vision.providers.enums import ProviderName


class AnalysisProviderFactory(BaseProviderFactory[AnalysisProvider, BaseProviderConfig]):
    @staticmethod
    def create(provider_name: ProviderName, config: BaseProviderConfig | None = None) -> AnalysisProvider:
        provider_class = AnalysisProviderRegistry.get(provider_name)
        return BaseProviderFactory.build(
            provider_class, provider_name, config or BaseProviderConfig(), "analysis_vision"
        )
