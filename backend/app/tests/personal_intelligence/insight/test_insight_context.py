"""build_insight_context() - a thin SpecialistContext composer,
structurally identical to build_personal_intelligence_context()/
build_research_context(). No new context type.
"""

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.personal_intelligence.insight.context import build_insight_context
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.request import SpecialistRequest


def test_returns_a_plain_specialist_context():
    context = build_insight_context(AgentContext(organization_id=1), None)
    assert type(context) is SpecialistContext


def test_carries_the_given_agent_context_through_unchanged():
    agent_context = AgentContext(organization_id=7)
    context = build_insight_context(agent_context, None)
    assert context.agent_context is agent_context


def test_carries_the_given_request_through_unchanged():
    request = SpecialistRequest(objective="Detect patterns")
    context = build_insight_context(AgentContext(organization_id=1), request)
    assert context.request is request


def test_request_may_be_none():
    context = build_insight_context(AgentContext(organization_id=1), None)
    assert context.request is None


def test_identity_fields_delegate_to_the_agent_context():
    agent_context = AgentContext(organization_id=1)
    context = build_insight_context(agent_context, None)
    assert context.execution_id == agent_context.execution_id
    assert context.correlation_id == agent_context.correlation_id
    assert context.organization_id == agent_context.organization_id
    assert context.conversation_id == agent_context.conversation_id
