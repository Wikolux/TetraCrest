from enum import StrEnum


class ExecutionMode(StrEnum):
    """How an execution is meant to be scheduled.

    A plain enum, not a dataclass: none of these five modes carries any
    data of its own - each is a complete, self-describing policy name.
    (A future ScheduledExecution options bag - e.g. "run at this time" -
    would be a separate, dedicated type built when scheduling is actually
    implemented, not speculatively added here.)

    Declaring the mode is all this milestone does - no scheduler exists
    to act on it yet.
    """

    IMMEDIATE = "immediate"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    PARALLEL = "parallel"
    DISTRIBUTED = "distributed"
