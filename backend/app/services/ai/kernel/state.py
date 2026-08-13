from enum import StrEnum


class ExecutionState(StrEnum):
    """Where a kernel execution is in its lifecycle.

    A plain enum - a closed, permanent set of lifecycle stages every
    execution passes through regardless of which capability or provider
    is involved. ExecutionResponse references this instead of relying
    solely on success: `success` only distinguishes "worked" from
    "didn't," while state captures *how* it didn't (FAILED vs CANCELLED
    vs still RETRYING) or the fact that it never got that far (PENDING,
    VALIDATING, QUEUED).
    """

    PENDING = "pending"
    VALIDATING = "validating"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    FAILED = "failed"
    COMPLETED = "completed"
