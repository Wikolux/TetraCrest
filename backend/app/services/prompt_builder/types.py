from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptMessage:
    """One chat message, in the shape a future LLM provider's messages
    list expects.

    Frozen: a PromptMessage, once built, is a fact about what was sent -
    it should never be edited in place, only replaced.
    """

    role: str
    content: str


@dataclass(frozen=True)
class PromptSection:
    """One logical, human-inspectable section of a built prompt.

    Distinct from PromptMessage: sections describe the prompt's logical
    structure (for inspection, debugging, or a future non-chat provider),
    while messages are the actual chat-turn list a provider consumes.

    Frozen for the same reason as PromptMessage: immutable once built.
    """

    title: str
    content: str


@dataclass(frozen=True)
class PromptPackage:
    """The Prompt Builder's final output - what a future LLM Service will
    consume.

    system_prompt and messages are what an LLM provider actually needs;
    sections is the structured, section-by-section record of how the
    prompt was assembled, kept separate so nothing about the provider-
    facing shape needs to know how it was built.

    Frozen: a PromptPackage represents a completed prompt snapshot and
    must never be modified after construction - build a new one instead
    of mutating an existing one.

    prompt_version and context_item_count are metadata only - no
    timestamps, no provider information. context_item_count mirrors the
    originating ContextPackage.item_count, so a caller can tell how much
    retrieved context actually made it into this prompt without re-reading
    the ContextPackage itself.
    """

    system_prompt: str
    messages: list[PromptMessage] = field(default_factory=list)
    sections: list[PromptSection] = field(default_factory=list)
    estimated_tokens: int = 0
    prompt_version: str = "1.0"
    context_item_count: int = 0
