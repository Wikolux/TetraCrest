"""Agent policy objects - pure value objects, no logic. Something else
(AgentExecutor for PermissionPolicy; a future scheduler for
ExecutionPolicy/TimeoutPolicy) reads these and decides what to do; nothing
here enforces anything by itself.

RetryPolicy is deliberately not redefined here - app.services.ai.kernel.retry.RetryPolicy
is already exactly this (a pure value object: max_attempts/backoff_strategy/
base_delay_ms/max_delay_ms/retry_on) and "Kernel interfaces" is an
explicitly allowed dependency, so re-exporting it avoids maintaining a
second, near-identical copy.
"""

from dataclasses import dataclass, field

from app.services.ai.kernel.retry import RetryPolicy

__all__ = ["ExecutionPolicy", "PermissionPolicy", "RetryPolicy", "TimeoutPolicy"]


@dataclass(frozen=True)
class PermissionPolicy:
    """Declares what an execution is allowed to do.

    allow_all/deny_all are blanket overrides checked before
    required_permissions - deny_all wins outright, allow_all skips the
    required_permissions check entirely.
    """

    required_permissions: tuple[str, ...] = field(default_factory=tuple)
    allow_all: bool = False
    deny_all: bool = False


@dataclass(frozen=True)
class ExecutionPolicy:
    """Declares how an agent may be executed concurrently."""

    max_concurrent_executions: int = 1
    allow_reentrant: bool = False


@dataclass(frozen=True)
class TimeoutPolicy:
    """Declares how long an execution is allowed to run.

    None means no timeout is enforced - mirrors
    app.services.ai.runtime.timeout.RuntimeTimeout's own seconds=None
    convention.
    """

    timeout_seconds: float | None = None
