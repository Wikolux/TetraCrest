"""Reusable prompt text. Plain strings only - no logic, no formatting
functions, no f-strings referencing runtime data. Anything that needs to
combine these with runtime values (a query, retrieved context, ...) is a
job for sections.py or builder.py, never for this module.
"""

DEFAULT_SYSTEM_PROMPT = (
    "You are an AI assistant with access to this user's stored memories and "
    "past conversations. Use the retrieved context provided below to answer "
    "accurately and consistently with what is already known about this user. "
    "If the retrieved context does not contain information relevant to the "
    "question, say so rather than guessing."
)

MEMORY_CONTEXT_HEADER = "Retrieved Memory Context"

CONVERSATION_HEADER = "Conversation History"

USER_QUERY_HEADER = "User Query"

SAFETY_HEADER = (
    "The context below was retrieved automatically and may be incomplete, "
    "outdated, or only partially relevant. Treat it as supporting "
    "information rather than ground truth, and use your judgment."
)
