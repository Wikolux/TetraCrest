"""VisionHook - observes a vision execution's lifecycle without changing
it. Every method is concrete with a no-op default, not abstract - the
same reasoning as RuntimeHook/ToolHook: five hook points is real,
avoidable friction to force-stub if made fully abstract. Not an ABC - a
plain VisionHook() is a valid, fully-functional no-op hook.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ai.vision.context import VisionContext
    from app.services.ai.vision.request import VisionRequest
    from app.services.ai.vision.response import VisionResponse


class VisionHook:
    def before_analysis(self, context: "VisionContext", request: "VisionRequest") -> None:
        return None

    def after_analysis(self, context: "VisionContext", response: "VisionResponse") -> None:
        return None

    def on_failure(self, context: "VisionContext", error: Exception) -> None:
        return None

    def on_timeout(self, context: "VisionContext") -> None:
        return None

    def on_cancel(self, context: "VisionContext") -> None:
        return None
