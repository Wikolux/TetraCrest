from abc import ABC, abstractmethod

from app.services.ai.kernel.execution import ExecutionRequest, ExecutionResponse


class KernelMiddleware(ABC):
    """Common contract for anything that may transform a request or
    response as it flows through the kernel.

    Middleware may modify - before_execute() can return a changed
    ExecutionRequest (e.g. to inject metadata), after_execute() can
    return a changed ExecutionResponse (e.g. to redact a field) - which
    is what distinguishes it from KernelHook, which only ever observes.
    No implementations exist in this milestone; this is the contract
    future middleware (rate limiting, auth, redaction, ...) will
    implement.
    """

    @abstractmethod
    def before_execute(self, request: ExecutionRequest) -> ExecutionRequest:
        """Run before provider execution. Return the request to proceed
        with - typically the same request, or a modified one."""
        raise NotImplementedError

    @abstractmethod
    def after_execute(self, request: ExecutionRequest, response: ExecutionResponse) -> ExecutionResponse:
        """Run after provider execution succeeds. Return the response to
        proceed with - typically the same response, or a modified one."""
        raise NotImplementedError

    @abstractmethod
    def on_error(self, request: ExecutionRequest, error: Exception) -> None:
        """Run when provider execution raises. Observes the failure;
        does not change kernel control flow by itself."""
        raise NotImplementedError
