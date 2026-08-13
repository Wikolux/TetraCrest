import copy

from app.services.prompt_builder.renderers import render_messages, render_text
from app.services.prompt_builder.types import PromptMessage, PromptPackage, PromptSection


def _package():
    return PromptPackage(
        system_prompt="You are a helpful assistant.",
        messages=[
            PromptMessage(role="system", content="You are a helpful assistant."),
            PromptMessage(role="user", content="earlier question"),
            PromptMessage(role="system", content="user prefers dark mode"),
            PromptMessage(role="user", content="what theme do I like?"),
        ],
        sections=[
            PromptSection(title="Instructions", content="Be concise."),
            PromptSection(title="Retrieved Memory Context", content="user prefers dark mode"),
            PromptSection(title="Conversation History", content="user: earlier question"),
            PromptSection(title="User Query", content="what theme do I like?"),
        ],
        estimated_tokens=42,
        context_item_count=1,
    )


# --- render_messages -----------------------------------------------------------


def test_render_messages_returns_plain_role_content_dicts():
    package = _package()

    rendered = render_messages(package)

    assert rendered == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "earlier question"},
        {"role": "system", "content": "user prefers dark mode"},
        {"role": "user", "content": "what theme do I like?"},
    ]


def test_render_messages_preserves_order():
    package = _package()

    rendered = render_messages(package)

    assert [entry["role"] for entry in rendered] == ["system", "user", "system", "user"]


def test_render_messages_empty_messages_returns_empty_list():
    package = PromptPackage(system_prompt="x", messages=[])

    assert render_messages(package) == []


def test_render_messages_contains_no_provider_specific_keys():
    package = _package()

    rendered = render_messages(package)

    for entry in rendered:
        assert set(entry.keys()) == {"role", "content"}


def test_render_messages_does_not_mutate_the_package():
    package = _package()
    original = copy.deepcopy(package)

    render_messages(package)

    assert package == original


# --- render_text -----------------------------------------------------------------


def test_render_text_includes_system_prompt_first():
    package = _package()

    text = render_text(package)

    assert text.startswith("System Prompt:\nYou are a helpful assistant.")


def test_render_text_includes_every_section_in_order():
    package = _package()

    text = render_text(package)

    assert text.index("System Prompt:") < text.index("Instructions:")
    assert text.index("Instructions:") < text.index("Retrieved Memory Context:")
    assert text.index("Retrieved Memory Context:") < text.index("Conversation History:")
    assert text.index("Conversation History:") < text.index("User Query:")


def test_render_text_includes_all_content():
    package = _package()

    text = render_text(package)

    assert "Be concise." in text
    assert "user prefers dark mode" in text
    assert "user: earlier question" in text
    assert "what theme do I like?" in text


def test_render_text_returns_a_single_string():
    assert isinstance(render_text(_package()), str)


def test_render_text_with_no_sections_still_includes_system_prompt():
    package = PromptPackage(system_prompt="You are a helpful assistant.", sections=[])

    text = render_text(package)

    assert text == "System Prompt:\nYou are a helpful assistant."


def test_render_text_does_not_mutate_the_package():
    package = _package()
    original = copy.deepcopy(package)

    render_text(package)

    assert package == original


def test_render_text_is_deterministic():
    package = _package()

    assert render_text(package) == render_text(package)
