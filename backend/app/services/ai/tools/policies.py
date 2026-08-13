"""ToolExecutionPolicy - operating-system-level execution policy for the
Tool Framework (how deep a tool may be invoked from, how long it may run,
how it retries), distinct from PermissionPolicy (permissions.py, "is this
allowed at all").

RetryPolicy is reused directly from app.services.ai.kernel.retry rather
than redefined - it is already exactly this (a pure value object:
max_attempts/backoff_strategy/base_delay_ms/max_delay_ms/retry_on), and
"Must reuse Kernel interfaces. No duplication" is explicit for this
milestone.
"""

from dataclasses import dataclass, field

from app.services.ai.kernel.retry import RetryPolicy

__all__ = ["RetryPolicy", "ToolExecutionPolicy"]


@dataclass(frozen=True)
class ToolExecutionPolicy:
    maximum_depth: int = 5
    timeout_seconds: float | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
