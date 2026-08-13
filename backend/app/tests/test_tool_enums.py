from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolEventType, ToolPermission


def test_tool_category_has_every_documented_category():
    assert {member.value for member in ToolCategory} == {
        "filesystem",
        "python",
        "shell",
        "browser",
        "search",
        "database",
        "email",
        "calendar",
        "spreadsheet",
        "image",
        "video",
        "audio",
        "ocr",
        "http_api",
        "knowledge_graph",
        "mcp",
        "custom_business",
        "unknown",
    }


def test_tool_capability_has_every_documented_capability():
    assert {member.value for member in ToolCapability} == {
        "read",
        "write",
        "execute",
        "network",
        "generate",
        "analyze",
        "transform",
        "search",
    }


def test_tool_permission_has_every_documented_permission():
    assert {member.value for member in ToolPermission} == {
        "filesystem.read",
        "filesystem.write",
        "network",
        "email.send",
        "database.read",
        "database.write",
        "python.execute",
        "shell.execute",
        "calendar.write",
        "browser",
        "image.generate",
        "audio.generate",
        "video.generate",
        "custom",
    }


def test_tool_event_type_has_every_documented_event():
    assert {member.value for member in ToolEventType} == {
        "tool_started",
        "validation_started",
        "validation_completed",
        "permission_granted",
        "permission_denied",
        "execution_started",
        "execution_completed",
        "execution_failed",
        "tool_cancelled",
    }
