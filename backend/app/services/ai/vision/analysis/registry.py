from app.services.ai.shared.provider_registry import GenericProviderRegistry
from app.services.ai.vision.analysis.base_provider import AnalysisProvider
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.shared.exceptions import VisionProviderError


class AnalysisProviderRegistry(GenericProviderRegistry[ProviderName, type[AnalysisProvider]]):
    _registration_error = VisionProviderError
