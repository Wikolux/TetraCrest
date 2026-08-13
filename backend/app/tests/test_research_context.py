from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.research.context import build_research_context
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.request import SpecialistRequest


def test_build_research_context_returns_a_specialist_context():
    agent_context = AgentContext(organization_id=1)
    request = SpecialistRequest(objective="Prepare for an interview")

    context = build_research_context(agent_context, request)

    assert isinstance(context, SpecialistContext)
    assert context.agent_context is agent_context
    assert context.request is request


def test_build_research_context_never_duplicates_execution_identity():
    agent_context = AgentContext(organization_id=1, conversation_id=7)

    context = build_research_context(agent_context, SpecialistRequest(objective="x"))

    assert context.execution_id == agent_context.execution_id
    assert context.organization_id == 1
    assert context.conversation_id == 7
