"""Pure functions that build PromptSections from inputs.

Every function here only reads its arguments - none of them mutate a
ContextPackage, a ContextSection, a PromptMessage, or anything else
handed to them - and each returns a brand new PromptSection. No database
or LLM logic lives here, only text assembly.
"""

from app.services.context.types import ContextPackage
from app.services.prompt_builder.templates import (
    CONVERSATION_HEADER,
    MEMORY_CONTEXT_HEADER,
    SAFETY_HEADER,
    USER_QUERY_HEADER,
)
from app.services.prompt_builder.types import PromptMessage, PromptSection


def build_instruction_section(additional_instructions: str | None = None) -> PromptSection:
    """Safety/usage guidance for the retrieved context, plus any
    caller-supplied additional instructions appended after it."""
    content = SAFETY_HEADER
    if additional_instructions:
        content = f"{content}\n\n{additional_instructions}"
    return PromptSection(title="Instructions", content=content)


def build_context_section(context_package: ContextPackage) -> PromptSection:
    """One PromptSection representing the retrieved memory context.

    ContextPackage.sections already groups items by resource_type; rather
    than flattening every item's content into one undifferentiated blob,
    each ContextSection becomes its own labeled block within this
    section's content, so the resource-type boundaries ContextBuilder
    already established stay visible in the final text.
    """
    if not context_package.sections:
        return PromptSection(title=MEMORY_CONTEXT_HEADER, content="")

    blocks = []
    for section in context_package.sections:
        if not section.items:
            continue
        item_text = "\n\n".join(item.content for item in section.items)
        blocks.append(f"{section.resource_type}:\n{item_text}")

    return PromptSection(title=MEMORY_CONTEXT_HEADER, content="\n\n".join(blocks))


def build_conversation_section(conversation_history: list[PromptMessage] | None) -> PromptSection:
    """One PromptSection summarizing the prior conversation turns.

    Separate from how conversation_history is added to PromptPackage.messages
    - this section is the human-inspectable record, not the actual chat
    turns a provider will replay.
    """
    if not conversation_history:
        return PromptSection(title=CONVERSATION_HEADER, content="")

    content = "\n\n".join(f"{message.role}: {message.content}" for message in conversation_history)
    return PromptSection(title=CONVERSATION_HEADER, content=content)


def build_user_query_section(query: str) -> PromptSection:
    """The user's current query, as its own labeled section."""
    return PromptSection(title=USER_QUERY_HEADER, content=query)
