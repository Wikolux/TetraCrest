import copy
from datetime import datetime, timezone

from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.prompt_builder.sections import (
    build_context_section,
    build_conversation_section,
    build_instruction_section,
    build_user_query_section,
)
from app.services.prompt_builder.templates import (
    CONVERSATION_HEADER,
    MEMORY_CONTEXT_HEADER,
    SAFETY_HEADER,
    USER_QUERY_HEADER,
)
from app.services.prompt_builder.types import PromptMessage, PromptSection

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _context_item(resource_id, content, resource_type="memory"):
    return ContextItem(
        resource_type=resource_type, resource_id=resource_id, content=content, score=0.5, created_at=_NOW
    )


# --- build_instruction_section ------------------------------------------------


def test_instruction_section_uses_safety_header_by_default():
    section = build_instruction_section()

    assert section.title == "Instructions"
    assert section.content == SAFETY_HEADER


def test_instruction_section_appends_additional_instructions():
    section = build_instruction_section("Always answer in French.")

    assert SAFETY_HEADER in section.content
    assert "Always answer in French." in section.content


def test_instruction_section_returns_a_prompt_section():
    assert isinstance(build_instruction_section(), PromptSection)


# --- build_context_section ----------------------------------------------------


def test_context_section_empty_package_has_empty_content():
    package = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)

    section = build_context_section(package)

    assert section.title == MEMORY_CONTEXT_HEADER
    assert section.content == ""


def test_context_section_includes_item_content():
    package = ContextPackage(
        sections=[ContextSection(resource_type="memory", items=[_context_item(1, "user likes dark mode")])],
        estimated_tokens=5,
        item_count=1,
        truncated=False,
    )

    section = build_context_section(package)

    assert "user likes dark mode" in section.content


def test_context_section_preserves_separation_between_resource_types():
    package = ContextPackage(
        sections=[
            ContextSection(resource_type="memory", items=[_context_item(1, "memory content")]),
            ContextSection(
                resource_type="conversation_message", items=[_context_item(2, "message content", "conversation_message")]
            ),
        ],
        estimated_tokens=10,
        item_count=2,
        truncated=False,
    )

    section = build_context_section(package)

    assert "memory:" in section.content
    assert "conversation_message:" in section.content
    # the memory block comes before the conversation_message block, matching
    # ContextPackage.sections' own order
    assert section.content.index("memory:") < section.content.index("conversation_message:")


def test_context_section_skips_empty_sections():
    package = ContextPackage(
        sections=[
            ContextSection(resource_type="memory", items=[]),
            ContextSection(resource_type="conversation_message", items=[_context_item(1, "content", "conversation_message")]),
        ],
        estimated_tokens=0,
        item_count=1,
        truncated=False,
    )

    section = build_context_section(package)

    assert "memory:" not in section.content
    assert "conversation_message:" in section.content


def test_context_section_does_not_mutate_the_context_package():
    package = ContextPackage(
        sections=[ContextSection(resource_type="memory", items=[_context_item(1, "content")])],
        estimated_tokens=5,
        item_count=1,
        truncated=False,
    )
    original = copy.deepcopy(package)

    build_context_section(package)

    assert package == original


# --- build_conversation_section ------------------------------------------------


def test_conversation_section_empty_history_has_empty_content():
    section = build_conversation_section(None)

    assert section.title == CONVERSATION_HEADER
    assert section.content == ""


def test_conversation_section_empty_list_has_empty_content():
    section = build_conversation_section([])

    assert section.content == ""


def test_conversation_section_includes_each_message():
    history = [PromptMessage(role="user", content="hi"), PromptMessage(role="assistant", content="hello there")]

    section = build_conversation_section(history)

    assert "user: hi" in section.content
    assert "assistant: hello there" in section.content


def test_conversation_section_does_not_mutate_input():
    history = [PromptMessage(role="user", content="hi")]
    original = copy.deepcopy(history)

    build_conversation_section(history)

    assert history == original


# --- build_user_query_section ---------------------------------------------------


def test_user_query_section_contains_the_query():
    section = build_user_query_section("what did we discuss yesterday?")

    assert section.title == USER_QUERY_HEADER
    assert section.content == "what did we discuss yesterday?"
