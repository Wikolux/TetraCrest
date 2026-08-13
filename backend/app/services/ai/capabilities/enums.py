from enum import StrEnum


class Capability(StrEnum):
    """Every kind of thing this platform is designed to eventually let a
    provider do.

    Only CONVERSATION has any implementation behind it in this milestone
    (app.services.ai.conversation) - the rest exist here purely as a
    documented, tested taxonomy so a future capability (e.g. VISION) has
    an obvious, already-agreed-upon name to build against, without this
    enum needing to change when that work starts.
    """

    CONVERSATION = "conversation"
    EMBEDDING = "embedding"
    REASONING = "reasoning"
    VISION = "vision"
    SPEECH = "speech"
    IMAGE_GENERATION = "image_generation"
    RERANKING = "reranking"
    PLANNING = "planning"
    TOOL_CALLING = "tool_calling"
