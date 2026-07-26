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
