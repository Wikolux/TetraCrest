"""VisionMiddleware/VisionMiddlewarePipeline - built directly on
GenericMiddleware/GenericMiddlewarePipeline (app.services.ai.shared.middleware)
rather than hand-copying the onion-composition control flow a third time.
Exactly like Runtime middleware, "exactly like FastAPI middleware" - no
concrete middleware exists yet, only the contract and the composition
logic.
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from app.services.ai.shared.middleware import GenericMiddleware, GenericMiddlewarePipeline

if TYPE_CHECKING:
    from app.services.ai.vision.context import VisionContext
    from app.services.ai.vision.response import VisionResponse
    from app.services.ai.vision.shared.base_provider import BaseVisionProvider

VisionHandler = Callable[["VisionContext", "BaseVisionProvider"], "VisionResponse"]


class VisionMiddleware(GenericMiddleware):
    @abstractmethod
    def __call__(
        self, context: "VisionContext", provider: "BaseVisionProvider", call_next: VisionHandler
    ) -> "VisionResponse":
        raise NotImplementedError


@dataclass(frozen=True)
class VisionMiddlewarePipeline(GenericMiddlewarePipeline):
    pass
