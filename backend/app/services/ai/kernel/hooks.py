from abc import ABC, abstractmethod

from app.services.ai.kernel.execution import ExecutionRequest, ExecutionResponse


class KernelHook(ABC):
    """Common contract for anything that observes a kernel execution
    without being able to change it.

    Every method returns None - a hook (logging, metrics, auditing, ...)
    never feeds a value back into the request/response flow, unlike
    KernelMiddleware, whose before_execute()/after_execute() return the
    (possibly modified) request/response. This is the entire distinction
    between the two: middleware may modify, hooks only observe. No
    implementations exist in this milestone.
    """

    @abstractmethod
    def before_execution(self, request: ExecutionRequest) -> None:
        raise NotImplementedError

    @abstractmethod
    def after_execution(self, request: ExecutionRequest, response: ExecutionResponse) -> None:
        raise NotImplementedError

    @abstractmethod
    def execution_failed(self, request: ExecutionRequest, error: Exception) -> None:
        raise NotImplementedError
