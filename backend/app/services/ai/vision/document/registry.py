from app.services.ai.shared.provider_registry import GenericProviderRegistry
from app.services.ai.vision.document.base_provider import DocumentVisionProvider
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.shared.exceptions import VisionProviderError


class DocumentVisionProviderRegistry(GenericProviderRegistry[ProviderName, type[DocumentVisionProvider]]):
    _registration_error = VisionProviderError
