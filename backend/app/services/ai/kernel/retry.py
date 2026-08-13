from dataclasses import dataclass, field
from enum import StrEnum


class BackoffStrategy(StrEnum):
    """How the delay between retry attempts grows.

    A plain enum: each strategy name is a complete, self-describing
    policy identifier. The numeric parameters (base delay, max delay)
    live on RetryPolicy, not here, since they're the same shape
    regardless of which strategy is chosen.
    """

    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_WITH_JITTER = "exponential_with_jitter"


class RetryCondition(StrEnum):
    """What kind of failure a RetryPolicy applies to.

    Deliberately generic - not HTTP status codes or any provider's
    specific error taxonomy (the kernel has zero provider knowledge).
    A future capability runtime maps whatever a real provider actually
    raised onto one of these before consulting a RetryPolicy.
    """

    TRANSIENT_FAILURE = "transient_failure"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    ALL_FAILURES = "all_failures"


@dataclass(frozen=True)
class RetryPolicy:
    """Declares how retries should behave for an execution - not an
    implementation.

    This is purely the kernel's future retry abstraction: no retry loop
    exists anywhere in the kernel, and existing provider-level retry
    logic (e.g. OpenAIEmbeddingProvider's exponential backoff, built
    before this platform existed) is untouched and unrelated - it is not
    moved, wrapped, or replaced by this. A future kernel execution engine
    would read a RetryPolicy to decide whether/how to retry a failed
    execution.
    """

    max_attempts: int = 3
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay_ms: int = 500
    max_delay_ms: int | None = None
    retry_on: tuple[RetryCondition, ...] = field(
        default_factory=lambda: (RetryCondition.TRANSIENT_FAILURE,)
    )
