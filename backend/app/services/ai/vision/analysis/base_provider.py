"""AnalysisProvider - chart analysis, graph analysis, UI screenshot
analysis, architecture diagram analysis, flowchart interpretation.
"""

from abc import abstractmethod

from app.services.ai.vision.request import VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.base_provider import BaseVisionProvider


class AnalysisProvider(BaseVisionProvider):
    @abstractmethod
    def analyze(self, request: VisionRequest) -> VisionResponse:
        raise NotImplementedError
