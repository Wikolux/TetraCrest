"""Timeout wrapping for provider execution.

RuntimeTimeout is deliberately not a preemptive/forceful timeout: Python
cannot safely interrupt arbitrary synchronous code without threads or OS
signals, and threading is explicitly avoided here for the same reason
cancellation.py avoids it. run() executes the callable to completion and
then raises RuntimeTimeoutError if it took longer than allowed - a
retrospective "this took too long" check, not an in-flight abort. Real
in-flight stopping of a long-running or streaming call comes from
combining this with a CancellationToken the provider checks periodically;
RuntimeTimeout only ever detects the overrun after the call returns.

No provider-specific timeout logic exists anywhere here - the same
RuntimeTimeout wraps every provider identically regardless of vendor.
"""

import time
from typing import Callable, TypeVar

from app.services.ai.runtime.types import AIRuntimeError

T = TypeVar("T")


class RuntimeTimeoutError(AIRuntimeError):
    """Raised when a wrapped call exceeds its configured timeout."""


class RuntimeTimeout:
    """Wraps a callable with a timeout check.

    seconds=None means no timeout is enforced - run() simply calls
    through.
    """

    def __init__(self, seconds: float | None) -> None:
        self.seconds = seconds

    def run(self, func: Callable[..., T], *args, **kwargs) -> T:
        if self.seconds is None:
            return func(*args, **kwargs)

        start = time.monotonic()
        result = func(*args, **kwargs)
        elapsed = time.monotonic() - start
        if elapsed > self.seconds:
            raise RuntimeTimeoutError(
                f"Execution exceeded timeout of {self.seconds}s (took {elapsed:.3f}s)"
            )
        return result
