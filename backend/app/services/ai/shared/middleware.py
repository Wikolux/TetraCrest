"""GenericMiddleware/GenericMiddlewarePipeline - reusable onion-composition
middleware, generalized after the identical control flow (each middleware
wraps a call_next callable; the pipeline composes them from the outside
in, "exactly like FastAPI middleware") had already been hand-copied for
Runtime (app.services.ai.runtime.middleware) and Tools
(app.services.ai.tools.middleware) before Vision needed it a third time.

Runtime's and Tools' existing middleware are deliberately left untouched
- migrating them onto this base is a separate, lower-risk future cleanup.
Vision's VisionMiddleware/VisionMiddlewarePipeline are the first to build
directly on this shared base via subclassing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

GenericHandler = Callable[[Any, Any], Any]


class GenericMiddleware(ABC):
    @abstractmethod
    def __call__(self, context: Any, subject: Any, call_next: GenericHandler) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class GenericMiddlewarePipeline:
    middleware: tuple = field(default_factory=tuple)

    def run(self, context: Any, subject: Any, handler: GenericHandler) -> Any:
        chain = handler
        for middleware in reversed(self.middleware):
            chain = self._bind(middleware, chain)
        return chain(context, subject)

    @staticmethod
    def _bind(middleware: GenericMiddleware, call_next: GenericHandler) -> GenericHandler:
        def _wrapped(context: Any, subject: Any) -> Any:
            return middleware(context, subject, call_next)

        return _wrapped
