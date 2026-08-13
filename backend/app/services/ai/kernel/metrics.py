"""Generic, provider-independent execution metric models.

Pure value objects - nothing here collects a metric. A future execution
engine would populate one of these after running a capability runtime and
hand it off to whatever observability mechanism eventually exists.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenUsageReference:
    """A generic, kernel-native token-count reference.

    Deliberately not app.services.ai.shared.types.TokenUsage: the kernel
    imports nothing from elsewhere in app.services.ai, so it defines its
    own minimal equivalent here rather than depending on that type.
    """

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class CostEstimate:
    """A rough, provider-independent cost estimate for one execution."""

    amount: float
    currency: str = "USD"


@dataclass(frozen=True)
class ExecutionMetrics:
    """Generic measurements about one execution.

    latency_ms is time spent waiting on a provider specifically;
    duration_ms is the total wall-clock time for the whole execution
    (provider time plus kernel/middleware overhead) - kept as two
    separate fields since they can differ once middleware/hooks add
    their own overhead.

    execution_id is a plain string, not a SharedExecutionContext import
    (the kernel imports nothing from elsewhere in app.services.ai except
    context.py's one sanctioned exception - see kernel/types.py) - it
    exists so metrics aggregation can group/join by execution without
    ever inspecting an events list. Whoever builds an ExecutionMetrics
    (AgentExecutor today) is expected to set it from their own context.
    """

    latency_ms: float | None = None
    duration_ms: float | None = None
    retry_count: int = 0
    cost_estimate: CostEstimate | None = None
    token_usage: TokenUsageReference | None = None
    execution_id: str | None = None
