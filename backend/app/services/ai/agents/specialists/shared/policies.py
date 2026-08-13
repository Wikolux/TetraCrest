"""SpecialistExecutionPolicy - operating-system-level execution policy
shared by every specialist (how deep it may delegate/recurse, how long it
may run, how it retries) - the specialist-framework analogue of
app.services.ai.agents.executive.policies.ExecutivePolicy and
app.services.ai.tools.policies.ToolExecutionPolicy.

RetryPolicy is reused directly from app.services.ai.kernel.retry rather
than redefined - "Do NOT duplicate any subsystem" applies here exactly as
it did for the Tool Framework.
"""

from dataclasses import dataclass, field

from app.services.ai.kernel.retry import RetryPolicy

__all__ = ["RetryPolicy", "SpecialistExecutionPolicy"]


@dataclass(frozen=True)
class SpecialistExecutionPolicy:
    maximum_depth: int = 5
    timeout_seconds: float | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    allow_delegation: bool = True
