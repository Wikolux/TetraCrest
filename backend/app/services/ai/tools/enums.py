"""Every plain, closed-taxonomy enum used across the Tool Framework -
centralized here for the same reason app.services.ai.agents.enums
centralizes agent-framework enums: every richer file (registry, events,
permissions, ...) imports from here rather than redefining or duplicating
a taxonomy.
"""

from enum import StrEnum


class ToolCategory(StrEnum):
    """What kind of tool this is. Only architectural support is required
    this milestone - no concrete tool exists in any of these categories
    yet."""

    FILESYSTEM = "filesystem"
    PYTHON = "python"
    SHELL = "shell"
    BROWSER = "browser"
    SEARCH = "search"
    DATABASE = "database"
    EMAIL = "email"
    CALENDAR = "calendar"
    SPREADSHEET = "spreadsheet"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    OCR = "ocr"
    HTTP_API = "http_api"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    MCP = "mcp"
    CUSTOM_BUSINESS = "custom_business"
    UNKNOWN = "unknown"


class ToolCapability(StrEnum):
    """What a tool can *do* - distinct from ToolCategory (what *kind* of
    tool it is). A tool's category is fixed and singular; its capabilities
    are a set other subsystems (discovery, permission-adjacent matching)
    reason about."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    GENERATE = "generate"
    ANALYZE = "analyze"
    TRANSFORM = "transform"
    SEARCH = "search"


class ToolPermission(StrEnum):
    """Every permission a tool may require to operate. Values deliberately
    match the milestone's own dotted-namespace convention
    (filesystem.read, email.send, ...)."""

    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    NETWORK = "network"
    EMAIL_SEND = "email.send"
    DATABASE_READ = "database.read"
    DATABASE_WRITE = "database.write"
    PYTHON_EXECUTE = "python.execute"
    SHELL_EXECUTE = "shell.execute"
    CALENDAR_WRITE = "calendar.write"
    BROWSER = "browser"
    IMAGE_GENERATE = "image.generate"
    AUDIO_GENERATE = "audio.generate"
    VIDEO_GENERATE = "video.generate"
    CUSTOM = "custom"


class ToolEventType(StrEnum):
    TOOL_STARTED = "tool_started"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    TOOL_CANCELLED = "tool_cancelled"
