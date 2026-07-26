"""Shared string literals for the embedding/vector subsystem.

Single source of truth so resource-type and provider/store names are
never duplicated as ad-hoc string literals across factories, VectorId,
and settings defaults.
"""

RESOURCE_MEMORY = "memory"
RESOURCE_CONVERSATION_MESSAGE = "conversation_message"
RESOURCE_KNOWLEDGE = "knowledge"

VECTOR_STORE_NULL = "null"
VECTOR_STORE_PGVECTOR = "pgvector"

EMBEDDING_PROVIDER_OPENAI = "openai"
