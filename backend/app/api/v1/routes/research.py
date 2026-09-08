"""P7.15: the one, narrowly-scoped API entrypoint proving TetraCrest's
first genuinely operational, permission-governed real-world action -
never a generic `/agent/chat`, `/execute`, or command endpoint.

Authorization model (P7.15 §3, deliberately NOT a general resolver):
reaching this function's body already required a real, authenticated
user (get_current_db_user) and a known tenant (get_current_organization_id)
- FastAPI's own dependency resolution runs before this body ever
executes, so an unauthenticated/unidentified caller triggers zero external
calls, structurally. What this function ADDITIONALLY constructs is a
fixed, narrowly-scoped TECHNICAL capability policy for exactly this one
bounded workflow - NETWORK only, for a SEARCH-category tool - never
general user authorization or RBAC/ABAC. No such general authority source
exists in this codebase today (confirmed in Phase 0), and this route does
not pretend one does.
"""

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_db_user, get_current_organization_id
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.research import ResearchLookupRequest, ResearchLookupResponse
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.research.context import build_research_context
from app.services.ai.agents.specialists.research.research_agent import ResearchAgent
from app.services.ai.agents.specialists.shared.request import SpecialistRequest
from app.services.ai.agents.specialists.tool_adapter import ToolAdapter
from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.tools.enums import ToolPermission
from app.services.ai.tools.execution import ToolExecutor
from app.services.ai.tools.manager import ToolManager
from app.services.ai.tools.permissions import PermissionPolicy
from database import get_db

router = APIRouter(prefix="/research", tags=["research"])

# The one, fixed capability this endpoint ever grants - never derived
# from a user/role/organization policy, since none exists yet (P7.15 §3).
_RESEARCH_LOOKUP_POLICY = PermissionPolicy(granted_permissions=frozenset({ToolPermission.NETWORK}))


@router.post("/lookup", response_model=ResearchLookupResponse)
def lookup(
    payload: ResearchLookupRequest,
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> ResearchLookupResponse:
    tool_adapter = ToolAdapter(manager=ToolManager(executor=ToolExecutor(permission_policy=_RESEARCH_LOOKUP_POLICY)))
    agent = ResearchAgent(default_provider=ProviderName.OPENAI, tool_adapter=tool_adapter)

    shared = SharedExecutionContext(organization_id=organization_id, user_id=user.id)
    agent_context = AgentContext(shared=shared)
    # memory_allowed=False is a deliberate scope choice, not an oversight:
    # this bounded workflow never needs AgentMemory/AIMemoryService, and
    # not touching it avoids coupling this vertical slice to the
    # embedding pipeline's own configuration.
    request = SpecialistRequest(objective=payload.query, tools_allowed=True, web_allowed=True, memory_allowed=False)
    specialist_context = build_research_context(agent_context, request)

    response = agent.research(request, specialist_context)

    _record_audit(db, organization_id=organization_id, user_id=user.id, agent=agent, success=response.success)

    return ResearchLookupResponse(
        success=response.success, summary=response.summary, findings=response.findings, sources=response.sources, error=response.error
    )


def _record_audit(db: Session, *, organization_id: int, user_id: int, agent: ResearchAgent, success: bool) -> None:
    """P7.15 §18-§19: audit ownership lives here, at the application
    boundary surrounding the governed action - never inside ResearchAgent
    or ToolExecutor. Deliberately does not persist the raw query, prompt,
    model response, or Wikipedia content - only structured, technical
    metadata sufficient to answer "what/who/authorized/executed/success"
    (P7.15 §17), reusing the existing AuditLog model, never a new
    telemetry/privacy subsystem."""
    details = json.dumps(
        {
            "tool_id": "wikipedia_search",
            "agent_id": agent.identity.agent_id,
            "permission": ToolPermission.NETWORK.value,
            "authorized": True,
            "executed": True,
            "success": success,
        }
    )
    AuditLogRepository(db).create(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="research.lookup",
            resource_type="tool_invocation",
            details=details,
        )
    )
