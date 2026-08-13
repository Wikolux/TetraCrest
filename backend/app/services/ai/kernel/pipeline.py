from dataclasses import dataclass, field

from app.services.ai.kernel.execution import ExecutionRequest, ExecutionResponse
from app.services.ai.kernel.hooks import KernelHook
from app.services.ai.kernel.middleware import KernelMiddleware


@dataclass(frozen=True)
class RuntimePipeline:
    """The fixed shape every kernel execution flows through:

        Request -> Middleware -> Provider Resolution -> Execution -> Hooks -> Response

    A pure composition object: it holds the ordered middleware and hooks
    a KernelRuntime will run (as immutable tuples - "no mutation
    guarantees" applies here too), but does not itself resolve or execute
    a provider. run() documents the intended flow and raises
    NotImplementedError - provider resolution and execution are not
    implemented in this milestone.
    """

    middleware: tuple[KernelMiddleware, ...] = field(default_factory=tuple)
    hooks: tuple[KernelHook, ...] = field(default_factory=tuple)

    def run(self, request: ExecutionRequest) -> ExecutionResponse:
        raise NotImplementedError(
            "RuntimePipeline.run is architecture only in this milestone - "
            "provider resolution and execution are not implemented yet."
        )
