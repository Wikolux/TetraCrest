#!/usr/bin/env python
"""Opt-in, real-network smoke test for OpenAIConversationProvider (P7.14).

Proves TetraCrest can send one real prompt to the real OpenAI API and get
a real response back, through the actual production path - not a fake,
not a mock:

    RuntimeAdapter -> AIRuntime -> RuntimeExecutor
    -> ConversationProviderFactory -> ConversationProviderRegistry
    -> OpenAIConversationProvider -> https://api.openai.com

Run explicitly, with real credentials, only when you actually want to
make one real, billed API call:

    OPENAI_API_KEY=sk-... python scripts/openai_live_smoke_test.py

This is deliberately NOT invoked by the FastAPI app and NOT invoked by
the test suite (pytest never imports this module - it isn't named
test_*.py, and app/tests/test_openai_conversation_provider.py proves the
same provider/registry/factory/runtime contract entirely with mocked
HTTP transport, requiring no credentials and no network access). Running
this script is a deliberate, manual, credentialed action - exactly like
scripts/initialize_vector_store.py's own precedent for out-of-band,
opt-in operations kept separate from both request handling and testing.

Never prints the API key, the full resolved configuration, or any user
context - only a short, safe summary of what happened.
"""

import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter  # noqa: E402
from app.services.ai.providers.enums import ProviderName  # noqa: E402
from app.services.ai.runtime.types import RuntimeRequest  # noqa: E402
from app.services.prompt_builder.types import PromptMessage, PromptPackage  # noqa: E402
from settings import get_settings  # noqa: E402


def main() -> int:
    settings = get_settings()
    if not settings.openai_api_key:
        print("BLOCKED: OPENAI_API_KEY is not configured in this environment.")
        print("Set it and re-run: OPENAI_API_KEY=sk-... python scripts/openai_live_smoke_test.py")
        return 1

    print(f"Using model: {settings.conversation_model} (provider: openai)")
    print("Sending one real prompt through RuntimeAdapter -> AIRuntime -> OpenAIConversationProvider ...")

    prompt_package = PromptPackage(
        system_prompt="You are a terse assistant. Reply with exactly three words.",
        messages=[PromptMessage(role="user", content="Say hello.")],
    )
    request = RuntimeRequest(
        organization_id=0,
        prompt_package=prompt_package,
        provider=ProviderName.OPENAI,
        max_tokens=20,
    )

    response = RuntimeAdapter().execute(request)

    if not response.success:
        print(f"FAILED: {response.error}")
        return 1

    print("SUCCESS")
    print(f"  provider: {response.provider}")
    print(f"  model: {response.conversation_response.model}")
    print(f"  finish_reason: {response.conversation_response.finish_reason.value}")
    print(f"  latency_ms: {response.latency_ms:.1f}")
    if response.usage:
        print(f"  usage: prompt={response.usage.prompt_tokens} completion={response.usage.completion_tokens} total={response.usage.total_tokens}")
    print(f"  response text: {response.conversation_response.text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
