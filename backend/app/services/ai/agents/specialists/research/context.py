"""Research-specific context construction - a thin convenience layer over
SpecialistContext (app.services.ai.agents.specialists.shared.context),
never a parallel context type. Execution identity is never duplicated:
build_research_context() only ever combines an existing AgentContext with
a SpecialistRequest into the one SpecialistContext shape every specialist
already uses.
"""

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.request import SpecialistRequest


def build_research_context(agent_context: AgentContext, request: SpecialistRequest) -> SpecialistContext:
    return SpecialistContext(agent_context=agent_context, request=request)
