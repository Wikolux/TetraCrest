"""Discovery-specific context construction - a thin convenience layer over
SpecialistContext, never a parallel context type. Identical in shape and
purpose to build_research_context/build_personal_intelligence_context.
"""

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.request import SpecialistRequest


def build_discovery_context(agent_context: AgentContext, request: SpecialistRequest) -> SpecialistContext:
    return SpecialistContext(agent_context=agent_context, request=request)
