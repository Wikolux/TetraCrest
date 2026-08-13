from app.services.ai.kernel.context import ExecutionContext
from app.services.ai.kernel.execution import ExecutionRequest, ExecutionResponse
from app.services.ai.kernel.pipeline import RuntimePipeline
from app.services.ai.kernel.registry import RuntimeRegistry


class KernelRuntime:
    """The central execution runtime every future request flows through:

        Agents -> Capabilities -> KernelRuntime -> Providers

    Capabilities never call a provider directly, and providers never know
    who called them - KernelRuntime is the one seam in between. It is
    constructed with its own RuntimeRegistry/RuntimePipeline via
    constructor injection, never a global or singleton - "no global
    state" applies to the runtime itself, not just its registry.

    This milestone is architecture only. execute()'s full intended
    responsibility chain is:

        1. validate request         (implemented - pure structural checks)
        2. resolve provider         (not implemented)
        3. run middleware           (not implemented)
        4. execute provider         (not implemented)
        5. run hooks                (not implemented)
        6. return ExecutionResponse (not implemented)

    Only step 1 has real behavior in this milestone, because it's pure
    structural validation with no provider or capability knowledge -
    everything from provider resolution onward requires a real provider
    registry/execution path that does not exist yet, so execute() raises
    NotImplementedError once validation passes.
    """

    def __init__(
        self,
        registry: RuntimeRegistry | None = None,
        pipeline: RuntimePipeline | None = None,
    ):
        self.registry = registry or RuntimeRegistry()
        self.pipeline = pipeline or RuntimePipeline(
            middleware=self.registry.get_middleware(), hooks=self.registry.get_hooks()
        )

    def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        self._validate(request)
        raise NotImplementedError(
            "KernelRuntime.execute is architecture only in this milestone - "
            "provider resolution, middleware, provider execution, and hooks "
            "are not implemented yet."
        )

    @staticmethod
    def _validate(request: ExecutionRequest) -> None:
        """Pure structural validation - no provider or capability logic.

        Deliberately the only real behavior in this milestone: it checks
        the shape of the request itself, never anything about what a
        capability or provider would do with it.
        """
        if not isinstance(request, ExecutionRequest):
            raise TypeError("KernelRuntime.execute requires an ExecutionRequest")
        if not request.capability:
            raise ValueError("ExecutionRequest.capability must be a non-empty string")
        if not isinstance(request.context, ExecutionContext):
            raise TypeError("ExecutionRequest.context must be an ExecutionContext")
