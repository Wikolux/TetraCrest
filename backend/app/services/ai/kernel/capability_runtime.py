from abc import ABC, abstractmethod

from app.services.ai.kernel.execution import ExecutionRequest, ExecutionResponse


class CapabilityRuntime(ABC):
    """The contract every future capability runtime will implement -
    ConversationRuntime, VisionRuntime, ReasoningRuntime, PlanningRuntime,
    SpeechRuntime, ToolRuntime, MemoryRuntime, and others not yet named.

    This is the seam that makes "capabilities do not directly invoke
    providers" hold at the code level: KernelRuntime is meant to
    eventually execute CapabilityRuntime implementations rather than
    reaching into a provider directly, and a capability runtime is meant
    to sit between the kernel and whatever provider(s) it needs -
    providers still never know who called them.

    Not wired into KernelRuntime.execute() yet - only the contract is
    established in this milestone. No concrete CapabilityRuntime exists.
    """

    @abstractmethod
    def validate(self, request: ExecutionRequest) -> None:
        """Check that request is well-formed for this capability.
        Raise on invalid input; return nothing on success."""
        raise NotImplementedError

    @abstractmethod
    def prepare(self, request: ExecutionRequest) -> ExecutionRequest:
        """Perform any capability-specific setup/transformation needed
        before execution, returning the (possibly modified) request that
        should actually be executed."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        """Run this capability for the given request and return a
        normalized ExecutionResponse."""
        raise NotImplementedError

    @abstractmethod
    def cleanup(self, request: ExecutionRequest) -> None:
        """Release any resources prepare()/execute() may have acquired."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """Return whether this capability runtime is currently able to
        serve requests."""
        raise NotImplementedError
