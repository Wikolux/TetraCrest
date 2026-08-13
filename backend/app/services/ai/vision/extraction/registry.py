from app.services.ai.shared.provider_registry import GenericProviderRegistry
from app.services.ai.vision.extraction.base_provider import ExtractionProvider
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.shared.exceptions import VisionProviderError


class ExtractionProviderRegistry(GenericProviderRegistry[ProviderName, type[ExtractionProvider]]):
    _registration_error = VisionProviderError
