"""RuntimeAdapter - a thin wrapper over the existing AIRuntime. Never
calls a provider directly (never touches ConversationProviderFactory/
ConversationProviderRegistry itself) - every call passes straight through
to the one existing entry point every agent uses.
"""

from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse


class RuntimeAdapter:
    def __init__(self, runtime: AIRuntime | None = None) -> None:
        self.runtime = runtime or AIRuntime()

    def execute(self, request: RuntimeRequest) -> RuntimeResponse:
        return self.runtime.execute(request)
