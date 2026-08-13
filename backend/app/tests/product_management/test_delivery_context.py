"""build_delivery_context - mirrors test_discovery_context.py's/
test_decision_context.py's own coverage: a thin composition, never a
parallel context type.
"""

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.product_management.delivery.context import build_delivery_context
from app.services.ai.agents.specialists.shared.request import SpecialistRequest


def test_composes_agent_context_and_request():
    agent_context = AgentContext(organization_id=1)
    request = SpecialistRequest(objective="draft this spec")

    context = build_delivery_context(agent_context, request)

    assert context.agent_context is agent_context
    assert context.request is request


def test_shared_execution_context_delegates_to_agent_context():
    agent_context = AgentContext(organization_id=7)
    context = build_delivery_context(agent_context, SpecialistRequest(objective="x"))

    assert context.organization_id == 7
    assert context.shared is agent_context.shared
