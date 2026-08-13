"""Cooperative execution cancellation.

Deliberately simple: no threading primitives, no asyncio. A
CancellationToken is a plain mutable flag a caller holding a reference to
the same token can flip from anywhere, and that RuntimeExecutor (and, in
the future, a long-running or streaming provider call) checks periodically
between steps. Nothing here forcibly interrupts a call in progress - the
callee has to check the token and stop itself.
"""


class CancellationToken:
    """A cooperative cancellation signal shared between a caller and the
    Runtime executing a request on its behalf.
    """

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        """Signal that the associated execution should stop."""
        self._cancelled = True

    def cancelled(self) -> bool:
        """Return whether cancel() has been called."""
        return self._cancelled
