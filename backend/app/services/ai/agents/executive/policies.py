"""ExecutivePolicy - operating-system-level policy for the Executive
itself (how deep delegation may nest, whether web/tools are allowed at
all, how many tasks may run in parallel), distinct from
app.services.ai.agents.policies (per-agent execution policy) and
app.services.ai.runtime's RuntimeTimeout/RetryPolicy (per-provider-call
policy). Pure value object - no logic; the Executive reads these, they
don't enforce themselves.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutivePolicy:
    maximum_depth: int = 5
    maximum_retries: int = 3
    maximum_runtime_seconds: float | None = None
    allow_web: bool = False
    allow_tools: bool = False
    allow_delegation: bool = True
    maximum_parallel_tasks: int = 1
