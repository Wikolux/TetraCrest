"""Strategy-specific context construction - a thin convenience layer over
SpecialistContext, mirroring build_discovery_context/build_decision_context/
build_delivery_context exactly. Never a parallel context type.
"""

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.request import SpecialistRequest


def build_strategy_context(agent_context: AgentContext, request: SpecialistRequest) -> SpecialistContext:
    return SpecialistContext(agent_context=agent_context, request=request)
