"""ExtractionProvider - OCR, table extraction, structured data extraction,
key-value extraction.
"""

from abc import abstractmethod

from app.services.ai.vision.request import VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.base_provider import BaseVisionProvider


class ExtractionProvider(BaseVisionProvider):
    @abstractmethod
    def extract(self, request: VisionRequest) -> VisionResponse:
        raise NotImplementedError
