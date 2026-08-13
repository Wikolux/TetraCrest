from app.services.ai.tools.shared.exceptions import (
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolPermissionError,
    ToolValidationError,
)


def test_tool_error_is_an_exception():
    assert issubclass(ToolError, Exception)


def test_tool_not_found_error_is_a_tool_error():
    assert issubclass(ToolNotFoundError, ToolError)


def test_tool_validation_error_is_a_tool_error():
    assert issubclass(ToolValidationError, ToolError)


def test_tool_permission_error_is_a_tool_error():
    assert issubclass(ToolPermissionError, ToolError)


def test_tool_execution_error_is_a_tool_error():
    assert issubclass(ToolExecutionError, ToolError)


def test_tool_error_can_be_raised_and_caught():
    try:
        raise ToolNotFoundError("missing tool")
    except ToolError as exc:
        assert str(exc) == "missing tool"
