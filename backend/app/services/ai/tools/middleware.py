"""Tool middleware - identical in philosophy to Runtime middleware
(app.services.ai.runtime.middleware): each ToolMiddleware wraps the next
collaborator in the chain via a `call_next` callable it decides whether,
when, and how to invoke. ToolMiddlewarePipeline composes an ordered chain
around a final handler the same way FastAPI composes ASGI middleware
around a route handler.

Built on GenericMiddleware/GenericMiddlewarePipeline
(app.services.ai.shared.middleware) rather than hand-rolling the onion-
composition control flow a third time - the same base Runtime and Vision
middleware use. ToolMiddleware/ToolMiddlewarePipeline keep their own typed
signature (ToolContext/BaseTool/ToolResult) and their original names; only
the composition logic is now shared.

No concrete middleware exists yet - only the contract and the composition
logic.
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from app.services.ai.shared.middleware import GenericMiddleware, GenericMiddlewarePipeline

if TYPE_CHECKING:
    from app.services.ai.tools.base_tool import BaseTool
    from app.services.ai.tools.context import ToolContext
    from app.services.ai.tools.result import ToolResult

ToolHandler = Callable[["ToolContext", "BaseTool"], "ToolResult"]


class ToolMiddleware(GenericMiddleware):
    @abstractmethod
    def __call__(self, context: "ToolContext", tool: "BaseTool", call_next: ToolHandler) -> "ToolResult":
        raise NotImplementedError


@dataclass(frozen=True)
class ToolMiddlewarePipeline(GenericMiddlewarePipeline):
    pass
