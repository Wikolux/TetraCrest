"""Shared enums for the embedding/vector subsystem.

Single source of truth for resource-type and provider/store names, used
consistently across factories, settings, VectorId, and metadata
generation instead of ad-hoc string literals. Each is a StrEnum, so a
member behaves exactly like its plain string value everywhere - equality,
hashing (dict keys), f-strings, and JSON serialization all just work -
while still giving callers a closed, discoverable set of valid values.
"""

from enum import StrEnum


class ResourceType(StrEnum):
    MEMORY = "memory"
    CONVERSATION_MESSAGE = "conversation_message"
    KNOWLEDGE = "knowledge"


class EmbeddingProviderName(StrEnum):
    OPENAI = "openai"


class VectorStoreProviderName(StrEnum):
    NULL = "null"
    PGVECTOR = "pgvector"


class MetricsRecorderName(StrEnum):
    LOGGING = "logging"


class ExecutionStatus(StrEnum):
    """P7.16: the smallest durable lifecycle for one operational
    execution - deliberately just STARTED/SUCCEEDED/FAILED, not a
    generic workflow-state machine. STARTED means "Tetra durably
    recorded this operation and began the execution workflow" - it is
    never itself proof that an external system received anything, and a
    record left at STARTED (never reaching a terminal status) is the
    intentional, honest signal that no terminal outcome was durably
    recorded, not an error state to hide or a claim about what actually
    happened externally. Terminal statuses (SUCCEEDED/FAILED) are
    immutable once set (ExecutionRecordRepository enforces this, not
    this enum itself) - no UNKNOWN/RETRYING/AWAITING_APPROVAL/etc. member
    exists yet; one would only be added once a real reconciliation
    mechanism exists to assign it, per P7.16's own explicit scope."""

    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
