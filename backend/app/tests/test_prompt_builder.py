import copy
from datetime import datetime, timezone

from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.prompt_builder.builder import PromptBuilder
from app.services.prompt_builder.templates import DEFAULT_SYSTEM_PROMPT
from app.services.prompt_builder.types import PromptMessage, PromptPackage

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _context_item(resource_id, content, resource_type="memory"):
    return ContextItem(
        resource_type=resource_type, resource_id=resource_id, content=content, score=0.5, created_at=_NOW
    )


def _empty_context_package():
    return ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)


def _populated_context_package():
    return ContextPackage(
        sections=[
            ContextSection(resource_type="memory", items=[_context_item(1, "user prefers dark mode")]),
        ],
        estimated_tokens=10,
        item_count=1,
        truncated=False,
    )


# --- default / custom system prompt ------------------------------------------


def test_uses_default_system_prompt_when_none_given():
    package = PromptBuilder().build("hello", _empty_context_package())

    assert package.system_prompt == DEFAULT_SYSTEM_PROMPT
    assert package.messages[0] == PromptMessage(role="system", content=DEFAULT_SYSTEM_PROMPT)


def test_uses_custom_system_prompt_when_given():
    package = PromptBuilder().build("hello", _empty_context_package(), system_prompt="Be terse.")

    assert package.system_prompt == "Be terse."
    assert package.messages[0] == PromptMessage(role="system", content="Be terse.")


def test_empty_string_system_prompt_is_respected_not_replaced_with_default():
    # an explicit empty string is a real (if unusual) override - only
    # `None` means "use the default"
    package = PromptBuilder().build("hello", _empty_context_package(), system_prompt="")

    assert package.system_prompt == ""


# --- empty / populated ContextPackage -----------------------------------------


def test_empty_context_package_produces_no_context_message():
    package = PromptBuilder().build("hello", _empty_context_package())

    assert not any("dark mode" in m.content for m in package.messages)
    # system + user query only - no context message inserted
    assert len(package.messages) == 2


def test_empty_context_package_still_produces_a_context_section_with_empty_content():
    package = PromptBuilder().build("hello", _empty_context_package())

    context_sections = [s for s in package.sections if s.title == "Retrieved Memory Context"]
    assert len(context_sections) == 1
    assert context_sections[0].content == ""


def test_populated_context_package_produces_a_context_message():
    package = PromptBuilder().build("hello", _populated_context_package())

    assert any("user prefers dark mode" in m.content for m in package.messages)


def test_populated_context_package_produces_a_context_section_with_content():
    package = PromptBuilder().build("hello", _populated_context_package())

    context_sections = [s for s in package.sections if s.title == "Retrieved Memory Context"]
    assert "user prefers dark mode" in context_sections[0].content


# --- empty / populated conversation history -----------------------------------


def test_empty_conversation_history_produces_no_conversation_section():
    package = PromptBuilder().build("hello", _empty_context_package(), conversation_history=[])

    assert not any(s.title == "Conversation History" for s in package.sections)


def test_none_conversation_history_produces_no_conversation_section():
    package = PromptBuilder().build("hello", _empty_context_package(), conversation_history=None)

    assert not any(s.title == "Conversation History" for s in package.sections)


def test_populated_conversation_history_produces_a_conversation_section():
    history = [PromptMessage(role="user", content="hi"), PromptMessage(role="assistant", content="hello!")]

    package = PromptBuilder().build("hello", _empty_context_package(), conversation_history=history)

    conversation_sections = [s for s in package.sections if s.title == "Conversation History"]
    assert len(conversation_sections) == 1
    assert "hi" in conversation_sections[0].content
    assert "hello!" in conversation_sections[0].content


def test_populated_conversation_history_messages_appear_in_messages_list():
    history = [PromptMessage(role="user", content="hi"), PromptMessage(role="assistant", content="hello!")]

    package = PromptBuilder().build("hello", _empty_context_package(), conversation_history=history)

    assert history[0] in package.messages
    assert history[1] in package.messages


# --- additional instructions ---------------------------------------------------


def test_additional_instructions_appear_in_instruction_section():
    package = PromptBuilder().build(
        "hello", _empty_context_package(), additional_instructions="Always cite your sources."
    )

    instruction_sections = [s for s in package.sections if s.title == "Instructions"]
    assert "Always cite your sources." in instruction_sections[0].content


def test_additional_instructions_do_not_appear_as_a_separate_message():
    package = PromptBuilder().build(
        "hello", _empty_context_package(), additional_instructions="Always cite your sources."
    )

    assert not any("Always cite your sources." in m.content for m in package.messages)


def test_no_additional_instructions_still_produces_an_instruction_section():
    package = PromptBuilder().build("hello", _empty_context_package())

    assert any(s.title == "Instructions" for s in package.sections)


# --- section ordering -----------------------------------------------------------


def test_section_order_without_history_is_instructions_context_query():
    package = PromptBuilder().build("hello", _populated_context_package())

    assert [s.title for s in package.sections] == ["Instructions", "Retrieved Memory Context", "User Query"]


def test_section_order_with_history_is_instructions_context_conversation_query():
    history = [PromptMessage(role="user", content="hi")]

    package = PromptBuilder().build("hello", _populated_context_package(), conversation_history=history)

    assert [s.title for s in package.sections] == [
        "Instructions",
        "Retrieved Memory Context",
        "Conversation History",
        "User Query",
    ]


# --- message ordering ------------------------------------------------------------


def test_message_order_without_history_or_context_is_system_then_user():
    package = PromptBuilder().build("hello", _empty_context_package())

    assert [m.role for m in package.messages] == ["system", "user"]


def test_message_order_with_history_and_context_is_system_history_context_query():
    history = [PromptMessage(role="user", content="earlier question")]

    package = PromptBuilder().build("hello", _populated_context_package(), conversation_history=history)

    assert [m.role for m in package.messages] == ["system", "user", "system", "user"]
    assert package.messages[1] is history[0]
    assert "user prefers dark mode" in package.messages[2].content
    assert package.messages[3].content == "hello"


# --- estimated token calculation -------------------------------------------------


def test_estimated_tokens_sums_len_over_four_across_all_messages():
    package = PromptBuilder().build("a" * 40, _empty_context_package(), system_prompt="b" * 20)

    # system message: 20 // 4 = 5, user message: 40 // 4 = 10
    assert package.estimated_tokens == 15


def test_estimated_tokens_includes_context_message_when_present():
    context_package = ContextPackage(
        sections=[ContextSection(resource_type="memory", items=[_context_item(1, "c" * 40)])],
        estimated_tokens=10,
        item_count=1,
        truncated=False,
    )

    package = PromptBuilder().build("a" * 8, context_package, system_prompt="b" * 8)

    system_tokens = 8 // 4
    query_tokens = 8 // 4
    context_message = next(m for m in package.messages if "c" * 40 in m.content)
    context_tokens = len(context_message.content) // 4
    assert package.estimated_tokens == system_tokens + query_tokens + context_tokens


def test_estimated_tokens_is_zero_for_all_empty_content():
    package = PromptBuilder().build("", _empty_context_package(), system_prompt="")

    assert package.estimated_tokens == 0


# --- PromptPackage correctness ----------------------------------------------------


def test_build_returns_a_prompt_package():
    assert isinstance(PromptBuilder().build("hello", _empty_context_package()), PromptPackage)


# --- prompt metadata (Task 3) --------------------------------------------------


def test_prompt_version_defaults_to_one_point_zero():
    package = PromptBuilder().build("hello", _empty_context_package())

    assert package.prompt_version == "1.0"


def test_context_item_count_reflects_empty_context_package():
    package = PromptBuilder().build("hello", _empty_context_package())

    assert package.context_item_count == 0


def test_context_item_count_reflects_populated_context_package():
    package = PromptBuilder().build("hello", _populated_context_package())

    assert package.context_item_count == _populated_context_package().item_count == 1


def test_context_item_count_matches_context_package_with_multiple_items():
    context_package = ContextPackage(
        sections=[
            ContextSection(
                resource_type="memory",
                items=[_context_item(1, "first"), _context_item(2, "second"), _context_item(3, "third")],
            )
        ],
        estimated_tokens=30,
        item_count=3,
        truncated=False,
    )

    package = PromptBuilder().build("hello", context_package)

    assert package.context_item_count == 3


def test_prompt_package_has_all_expected_fields_populated():
    package = PromptBuilder().build("hello", _populated_context_package())

    assert isinstance(package.system_prompt, str)
    assert isinstance(package.messages, list)
    assert all(isinstance(m, PromptMessage) for m in package.messages)
    assert isinstance(package.sections, list)
    assert isinstance(package.estimated_tokens, int)


# --- deterministic output --------------------------------------------------------


def test_build_is_deterministic_for_identical_inputs():
    history = [PromptMessage(role="user", content="hi")]

    first = PromptBuilder().build("hello", _populated_context_package(), conversation_history=history)
    second = PromptBuilder().build("hello", _populated_context_package(), conversation_history=history)

    assert first == second


# --- no input mutation -------------------------------------------------------------


def test_build_does_not_mutate_the_context_package():
    context_package = _populated_context_package()
    original = copy.deepcopy(context_package)

    PromptBuilder().build("hello", context_package)

    assert context_package == original


def test_build_does_not_mutate_conversation_history():
    history = [PromptMessage(role="user", content="hi")]
    original = copy.deepcopy(history)

    PromptBuilder().build("hello", _empty_context_package(), conversation_history=history)

    assert history == original
