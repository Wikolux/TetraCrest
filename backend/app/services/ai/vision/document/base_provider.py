"""DocumentVisionProvider - document understanding: PDF understanding,
scanned documents, invoices, forms, contracts, reports.
"""

from abc import abstractmethod

from app.services.ai.vision.request import VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.base_provider import BaseVisionProvider


class DocumentVisionProvider(BaseVisionProvider):
    @abstractmethod
    def understand(self, request: VisionRequest) -> VisionResponse:
        raise NotImplementedError
