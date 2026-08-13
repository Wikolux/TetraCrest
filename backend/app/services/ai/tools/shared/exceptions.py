"""Root exception hierarchy for the Tool Framework - the same role
AIError/AgentError/KernelError play for their own subsystems.
"""


class ToolError(Exception):
    """Root exception for the Tool Framework."""


class ToolNotFoundError(ToolError):
    """Raised when a tool_id cannot be resolved to a registered tool."""


class ToolValidationError(ToolError):
    """Raised when input/output/schema validation fails."""


class ToolPermissionError(ToolError):
    """Raised when a tool's required permissions aren't granted by the
    PermissionPolicy currently in effect."""


class ToolExecutionError(ToolError):
    """Raised when a tool misbehaves at the contract level (e.g. execute()
    returns something other than a ToolResult) - distinct from a tool's
    own reported failure (ToolResult(success=False, ...)), which is not an
    exception at all."""
