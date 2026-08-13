from app.services.context.types import ContextPackage
from app.services.prompt_builder.sections import (
    build_context_section,
    build_conversation_section,
    build_instruction_section,
    build_user_query_section,
)
from app.services.prompt_builder.templates import DEFAULT_SYSTEM_PROMPT
from app.services.prompt_builder.types import PromptMessage, PromptPackage

_CHARS_PER_TOKEN = 4


class PromptBuilder:
    """Converts a query, retrieved context, and optional conversation
    history into a structured PromptPackage.

    Prompt construction only: no LLM call, no memory retrieval, no
    embedding generation, no ranking, no repository/database access -
    this class only ever transforms the arguments build() is given.
    Deterministic and side-effect free: the same arguments always produce
    an equal PromptPackage, and none of query/context_package/
    conversation_history are ever mutated.

    There is exactly one PromptBuilder - no factory, no provider
    abstraction. Nothing here is swappable in the way EmbeddingProvider or
    VectorStore are, so none of that machinery applies.
    """

    def build(
        self,
        query: str,
        context_package: ContextPackage,
        conversation_history: list[PromptMessage] | None = None,
        system_prompt: str | None = None,
        additional_instructions: str | None = None,
    ) -> PromptPackage:
        resolved_system_prompt = system_prompt if system_prompt is not None else DEFAULT_SYSTEM_PROMPT
        history = conversation_history or []

        instruction_section = build_instruction_section(additional_instructions)
        context_section = build_context_section(context_package)
        user_query_section = build_user_query_section(query)

        sections = [instruction_section, context_section]
        if history:
            sections.append(build_conversation_section(history))
        sections.append(user_query_section)

        messages = self._build_messages(resolved_system_prompt, history, context_section.content, query)
        estimated_tokens = self._estimate_tokens(messages)

        return PromptPackage(
            system_prompt=resolved_system_prompt,
            messages=messages,
            sections=sections,
            estimated_tokens=estimated_tokens,
            context_item_count=context_package.item_count,
        )

    @staticmethod
    def _build_messages(
        system_prompt: str,
        conversation_history: list[PromptMessage],
        context_content: str,
        query: str,
    ) -> list[PromptMessage]:
        """Assemble the chat-turn list in order: System, Conversation
        History (if any), Retrieved Context (if any), User Query.

        additional_instructions never becomes its own message here - it's
        represented only in the instruction PromptSection, not replayed to
        the provider as a separate chat turn.
        """
        messages = [PromptMessage(role="system", content=system_prompt)]
        messages.extend(conversation_history)
        if context_content:
            messages.append(PromptMessage(role="system", content=context_content))
        messages.append(PromptMessage(role="user", content=query))
        return messages

    @staticmethod
    def _estimate_tokens(messages: list[PromptMessage]) -> int:
        """len(content) // 4 per message, summed - the same lightweight,
        tokenizer-free heuristic ContextBuilder's BudgetStage uses. Since
        the system prompt is always messages[0], this estimate already
        covers it - no separate addition is needed on top.
        """
        return sum(len(message.content) // _CHARS_PER_TOKEN for message in messages)
