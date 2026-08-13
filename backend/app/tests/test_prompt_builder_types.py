import dataclasses

import pytest

from app.services.prompt_builder.types import PromptMessage, PromptPackage, PromptSection


def test_prompt_message_construction():
    message = PromptMessage(role="user", content="hello")

    assert message.role == "user"
    assert message.content == "hello"


def test_prompt_section_construction():
    section = PromptSection(title="Instructions", content="be helpful")

    assert section.title == "Instructions"
    assert section.content == "be helpful"


def test_prompt_package_defaults():
    package = PromptPackage(system_prompt="you are an assistant")

    assert package.system_prompt == "you are an assistant"
    assert package.messages == []
    assert package.sections == []
    assert package.estimated_tokens == 0
    assert package.prompt_version == "1.0"
    assert package.context_item_count == 0


def test_prompt_package_construction_with_all_fields():
    message = PromptMessage(role="user", content="hi")
    section = PromptSection(title="User Query", content="hi")

    package = PromptPackage(
        system_prompt="you are an assistant",
        messages=[message],
        sections=[section],
        estimated_tokens=5,
        prompt_version="2.0",
        context_item_count=3,
    )

    assert package.messages == [message]
    assert package.sections == [section]
    assert package.estimated_tokens == 5
    assert package.prompt_version == "2.0"
    assert package.context_item_count == 3


# --- immutability (Task 1) ----------------------------------------------------


def test_prompt_message_is_frozen():
    message = PromptMessage(role="user", content="hello")

    with pytest.raises(dataclasses.FrozenInstanceError):
        message.content = "changed"


def test_prompt_section_is_frozen():
    section = PromptSection(title="Instructions", content="be helpful")

    with pytest.raises(dataclasses.FrozenInstanceError):
        section.content = "changed"


def test_prompt_package_is_frozen():
    package = PromptPackage(system_prompt="you are an assistant")

    with pytest.raises(dataclasses.FrozenInstanceError):
        package.system_prompt = "changed"


def test_prompt_package_estimated_tokens_cannot_be_reassigned():
    package = PromptPackage(system_prompt="x", estimated_tokens=10)

    with pytest.raises(dataclasses.FrozenInstanceError):
        package.estimated_tokens = 20
