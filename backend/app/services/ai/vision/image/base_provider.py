"""ImageVisionProvider - image understanding: describe image, identify
objects, scene understanding, image classification, image captioning.

Adds exactly one abstract member (describe()) on top of BaseVisionProvider's
shared contract (health_check/provider_name/model_name required;
initialize/shutdown/capabilities/metadata concrete-with-safe-default) -
mirrors ConversationProvider's own fully-abstract-core-plus-safe-defaults
split.
"""

from abc import abstractmethod

from app.services.ai.vision.request import VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.base_provider import BaseVisionProvider


class ImageVisionProvider(BaseVisionProvider):
    @abstractmethod
    def describe(self, request: VisionRequest) -> VisionResponse:
        """Produce a VisionResponse for one or more images - never a
        provider SDK's own response object."""
        raise NotImplementedError
