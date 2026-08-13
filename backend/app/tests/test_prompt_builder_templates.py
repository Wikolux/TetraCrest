from app.services.prompt_builder import templates


def test_templates_are_all_non_empty_strings():
    for name in (
        "DEFAULT_SYSTEM_PROMPT",
        "MEMORY_CONTEXT_HEADER",
        "CONVERSATION_HEADER",
        "USER_QUERY_HEADER",
        "SAFETY_HEADER",
    ):
        value = getattr(templates, name)
        assert isinstance(value, str)
        assert value.strip() != ""


def test_templates_contain_no_format_placeholders():
    # templates are plain text only - no {}-style placeholders that would
    # imply logic/formatting belongs in this module
    for name in (
        "DEFAULT_SYSTEM_PROMPT",
        "MEMORY_CONTEXT_HEADER",
        "CONVERSATION_HEADER",
        "USER_QUERY_HEADER",
        "SAFETY_HEADER",
    ):
        value = getattr(templates, name)
        assert "{" not in value
        assert "}" not in value
