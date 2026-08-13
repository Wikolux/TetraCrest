"""Generic, kernel-only value objects.

The kernel imports nothing from elsewhere in app.services.ai (not
capabilities/, not providers/, not conversation/) - it only knows about
plain Python types - with exactly one sanctioned exception:
app.services.ai.kernel.context.ExecutionContext composes
app.services.ai.shared.execution_context.SharedExecutionContext, the AI
Operating System's single unified execution identity that Kernel,
Runtime, and Agents all now share rather than each redefining. That one
import lives in context.py only; every other kernel module, including
this one, still depends on nothing outside the kernel. Metadata and
Payload exist so every kernel dataclass that needs "an arbitrary read-only
bag of data" or "an opaque value" expresses that with the same one alias,
instead of each file spelling out its own Mapping[str, Any]/Any
independently.
"""

from typing import Any, Mapping

Metadata = Mapping[str, Any]
Payload = Any


class KernelError(Exception):
    """Root exception for the AI Operating System Kernel.

    No code currently raises this - KernelRuntime._validate() still
    raises plain TypeError/ValueError, and changing that would be a
    behavior change to an existing public interface with no compelling
    reason to make it now. KernelError exists so future kernel-level
    failures (execution errors, cancellation errors, retry-exhausted
    errors, ...) have one common, provider- and capability-independent
    root to subclass and to catch against, the same role AIProviderError
    plays at the platform layer - without this milestone guessing at the
    exact subclass hierarchy those future failures will need.
    """
