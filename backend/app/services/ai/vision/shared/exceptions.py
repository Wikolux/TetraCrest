"""Root exception hierarchy for the Vision Framework - the same role
AIError/AgentError/KernelError/ToolError play for their own subsystems.
"""


class VisionError(Exception):
    """Root exception for the Vision Framework."""


class VisionProviderError(VisionError):
    """Raised when a vision provider cannot be resolved or constructed -
    an unsupported/unregistered provider name, or a duplicate
    registration attempt."""


class VisionExecutionError(VisionError):
    """Raised when a vision provider misbehaves at the contract level
    (e.g. its method returns something other than a VisionResponse) -
    distinct from a provider's own reported failure
    (VisionResponse(success=False, ...)), which is not an exception at
    all."""
