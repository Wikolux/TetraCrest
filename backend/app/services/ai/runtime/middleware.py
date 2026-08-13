"""Runtime middleware - exactly like FastAPI middleware.

Each RuntimeMiddleware wraps the next collaborator in the chain (another
middleware, or ultimately the actual provider call) via a `call_next`
callable it decides whether, when, and how to invoke. MiddlewarePipeline
composes an ordered chain of middleware around a final handler the same
way FastAPI composes ASGI middleware around a route handler.

Built on GenericMiddleware/GenericMiddlewarePipeline
(app.services.ai.shared.middleware) rather than hand-rolling the onion-
composition control flow - the same base Tool and Vision middleware use.
RuntimeMiddleware/MiddlewarePipeline keep their original names and public
surface; only the implementation is now shared.

No concrete middleware exists yet - logging, metrics, cost tracking,
safety, prompt inspection, caching, and so on are all future work. Only
the contract and the composition logic exist in this milestone.
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable

from app.services.ai.runtime.types import RuntimeContext, RuntimeExecutionResult, RuntimeRequest
from app.services.ai.shared.middleware import GenericMiddleware, GenericMiddlewarePipeline

RuntimeHandler = Callable[[RuntimeContext, RuntimeRequest], RuntimeExecutionResult]


class RuntimeMiddleware(GenericMiddleware):
    """Contract for one link in the Runtime's middleware chain.

    __call__ receives the current context/request and a `call_next`
    callable representing the rest of the chain - it may inspect or
    transform the request before calling call_next, inspect or transform
    the result after, short-circuit by not calling call_next at all, or
    raise to abort the chain.
    """

    @abstractmethod
    def __call__(
        self,
        context: RuntimeContext,
        request: RuntimeRequest,
        call_next: RuntimeHandler,
    ) -> RuntimeExecutionResult:
        raise NotImplementedError


@dataclass(frozen=True)
class MiddlewarePipeline(GenericMiddlewarePipeline):
    """Composes an ordered chain of RuntimeMiddleware around a final handler.

    run() (inherited from GenericMiddlewarePipeline) builds the chain from
    the inside out: the final handler is wrapped by the last middleware,
    which is wrapped by the second-to-last, and so on, so the first
    middleware in `middleware` is the outermost - the first to see the
    request and the last to see the result, exactly like FastAPI middleware
    ordering.
    """
