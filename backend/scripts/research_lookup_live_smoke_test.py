#!/usr/bin/env python
"""Opt-in, real-network smoke test for the P7.15 governed real-world
action vertical slice.

Proves TetraCrest can execute the full, real chain - a real Wikipedia
lookup AND a real OpenAI model call - through the actual production
composition, not fakes:

    ResearchAgent (default_provider=OPENAI, tool_adapter=<real, governed>)
    -> ToolDiscovery -> ToolRegistry -> ToolExecutor (real PermissionPolicy)
    -> WikipediaSearchTool -> https://en.wikipedia.org
    -> ResearchSynthesizer
    -> RuntimeAdapter -> AIRuntime -> OpenAIConversationProvider -> https://api.openai.com

Run explicitly, with real credentials, only when you actually want to
make real, billed/rate-limited external calls:

    OPENAI_API_KEY=sk-... python scripts/research_lookup_live_smoke_test.py

This is deliberately NOT invoked by the FastAPI app and NOT invoked by
the test suite - app/tests/test_research_lookup_route.py already proves
the identical composition end to end with mocked HTTP transport, requiring
no credentials, no network, and no Wikipedia availability. Running this
script is a deliberate, manual, credentialed action - the same precedent
scripts/openai_live_smoke_test.py (P7.14) and
scripts/initialize_vector_store.py already established.

Never prints the API key, the full resolved configuration, or any
sensitive request content beyond the query you yourself pass in.
"""

import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.services.ai.agents.context import AgentContext  # noqa: E402
from app.services.ai.agents.specialists.research.context import build_research_context  # noqa: E402
from app.services.ai.agents.specialists.research.research_agent import ResearchAgent  # noqa: E402
from app.services.ai.agents.specialists.shared.request import SpecialistRequest  # noqa: E402
from app.services.ai.agents.specialists.tool_adapter import ToolAdapter  # noqa: E402
from app.services.ai.providers.enums import ProviderName  # noqa: E402
from app.services.ai.shared.execution_context import SharedExecutionContext  # noqa: E402
from app.services.ai.tools.enums import ToolPermission  # noqa: E402
from app.services.ai.tools.execution import ToolExecutor  # noqa: E402
from app.services.ai.tools.manager import ToolManager  # noqa: E402
from app.services.ai.tools.permissions import PermissionPolicy  # noqa: E402
from settings import get_settings  # noqa: E402


def main() -> int:
    settings = get_settings()
    if not settings.openai_api_key:
        print("BLOCKED: OPENAI_API_KEY is not configured in this environment.")
        print("Set it and re-run: OPENAI_API_KEY=sk-... python scripts/research_lookup_live_smoke_test.py")
        return 1

    query = sys.argv[1] if len(sys.argv) > 1 else "Python (programming language)"
    print(f"Query: {query!r}")
    print(f"Model: {settings.conversation_model} (provider: openai)")
    print("Running the real vertical slice - one real Wikipedia call, one real OpenAI call ...")

    policy = PermissionPolicy(granted_permissions=frozenset({ToolPermission.NETWORK}))
    tool_adapter = ToolAdapter(manager=ToolManager(executor=ToolExecutor(permission_policy=policy)))
    agent = ResearchAgent(default_provider=ProviderName.OPENAI, tool_adapter=tool_adapter)

    shared = SharedExecutionContext(organization_id=0, user_id=0)
    agent_context = AgentContext(shared=shared)
    request = SpecialistRequest(objective=query, tools_allowed=True, web_allowed=True, memory_allowed=False)
    specialist_context = build_research_context(agent_context, request)

    response = agent.research(request, specialist_context)

    if not response.success:
        print(f"FAILED: {response.error}")
        return 1

    print("SUCCESS")
    print(f"  summary: {response.summary!r}")
    print(f"  findings: {response.findings}")
    print(f"  sources: {response.sources}")
    print(f"  confidence: {response.confidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
