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

P7.16 adds the durable execution ledger, with an explicit division of
labor between the two durable records this route now writes:

- ExecutionRecord is the OPERATIONAL source of current execution state -
  written STARTED and committed BEFORE either external call (Wikipedia,
  OpenAI) is attempted, then updated to exactly one terminal status
  (SUCCEEDED/FAILED) once the bounded research workflow itself returns.
  A row left at STARTED means Tetra durably began the workflow but no
  terminal outcome was durably recorded - it does NOT by itself prove an
  external system received (or didn't receive) anything.
- AuditLog remains exactly what P7.15 built it as - supplementary,
  historical, write-once provenance - now additionally carrying the same
  execution_id/correlation_id so the two records can be joined, but never
  itself the authority on current state.

Both are best-effort from this route's own perspective in one specific
sense: a failure to WRITE the terminal ExecutionRecord update or the
AuditLog row must never retroactively turn an already-successful (or
already-known-failed) research result into a discarded one for the
client - see _try_persist()'s own docstring for exactly why and how.
"""

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_db_user, get_current_organization_id
from app.logging_utils import get_logger
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.execution_record_repository import ExecutionRecordRepository
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
logger = get_logger("research_lookup")

# The one, fixed capability this endpoint ever grants - never derived
# from a user/role/organization policy, since none exists yet (P7.15 §3).
_RESEARCH_LOOKUP_POLICY = PermissionPolicy(granted_permissions=frozenset({ToolPermission.NETWORK}))
_OPERATION = "research.lookup"
_MAX_ERROR_SUMMARY_LENGTH = 500


@router.post("/lookup", response_model=ResearchLookupResponse)
def lookup(
    payload: ResearchLookupRequest,
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> ResearchLookupResponse:
    tool_adapter = ToolAdapter(manager=ToolManager(executor=ToolExecutor(permission_policy=_RESEARCH_LOOKUP_POLICY)))
    agent = ResearchAgent(default_provider=ProviderName.OPENAI, tool_adapter=tool_adapter)

    # E0 - the one root execution identity shared by the durable ledger,
    # the AgentContext/SpecialistContext ResearchAgent executes under, and
    # (via RuntimeRequest.parent_shared, unchanged since P7.14) the child
    # identity RuntimeExecutor creates for the model call. P7.16 does not
    # persist that model-call child id (see this module's own docstring
    # and the P7.16 audit report §31) - only E0, the root operation.
    shared = SharedExecutionContext(organization_id=organization_id, user_id=user.id)
    execution_repo = ExecutionRecordRepository(db)

    # HARD REQUIREMENT (P7.16 §9): this commit must happen before either
    # external call (Wikipedia, OpenAI) is attempted. Nothing below this
    # line can run before it - proven by test, not just by this ordering.
    execution_repo.create_started(
        execution_id=shared.execution_id,
        correlation_id=shared.correlation_id,
        organization_id=organization_id,
        user_id=user.id,
        agent_id=agent.identity.agent_id,
        operation=_OPERATION,
    )

    agent_context = AgentContext(shared=shared)
    # memory_allowed=False is a deliberate scope choice, not an oversight:
    # this bounded workflow never needs AgentMemory/AIMemoryService, and
    # not touching it avoids coupling this vertical slice to the
    # embedding pipeline's own configuration.
    request = SpecialistRequest(objective=payload.query, tools_allowed=True, web_allowed=True, memory_allowed=False)
    specialist_context = build_research_context(agent_context, request)

    try:
        response = agent.research(request, specialist_context)
    except Exception:
        # ResearchAgent.research() is designed to never raise - this is
        # defense in depth for a genuinely unexpected failure, not the
        # normal path. A best-effort FAILED transition; if even this
        # fails, or if the process dies before it runs at all, the
        # record simply stays STARTED - exactly the intended, honest
        # signal (P7.16 §15/§17), never faked.
        _try_persist(db, "mark_failed_on_unexpected_exception", lambda: execution_repo.mark_failed(shared.execution_id, error_summary="Unexpected exception during research execution"))
        raise

    if response.success:
        _try_persist(db, "mark_succeeded", lambda: execution_repo.mark_succeeded(shared.execution_id))
    else:
        _try_persist(db, "mark_failed", lambda: execution_repo.mark_failed(shared.execution_id, error_summary=_bounded(response.error)))

    _try_persist(
        db,
        "record_audit",
        lambda: _record_audit(
            db,
            organization_id=organization_id,
            user_id=user.id,
            agent=agent,
            execution_id=shared.execution_id,
            correlation_id=shared.correlation_id,
            success=response.success,
        ),
    )

    # The client always receives the real research outcome, regardless of
    # whether the bookkeeping above fully succeeded (P7.16 §19/§21) - a
    # persistence failure in our own supplementary records must never
    # discard an already-produced, real answer.
    return ResearchLookupResponse(
        success=response.success, summary=response.summary, findings=response.findings, sources=response.sources, error=response.error
    )


def _try_persist(db: Session, action_description: str, fn) -> None:
    """Best-effort bookkeeping (P7.16 §19-§21): never lets a failure here
    discard an already-produced research result from reaching the
    client. On failure, rolls back the session first - a failed commit
    leaves SQLAlchemy's session in a failed-transaction state that would
    break any later write on the same session/request - then logs via
    the existing logging convention rather than silently swallowing with
    zero evidence (P7.16 §19's own explicit requirement)."""
    try:
        fn()
    except Exception:
        db.rollback()
        logger.warning(f"research_lookup_persistence_failed: {action_description}", exc_info=True)


def _bounded(text: str | None) -> str | None:
    if text is None:
        return None
    return text[:_MAX_ERROR_SUMMARY_LENGTH]


def _record_audit(
    db: Session, *, organization_id: int, user_id: int, agent: ResearchAgent, execution_id: str, correlation_id: str | None, success: bool
) -> None:
    """P7.15 §18-§19, extended by P7.16 §18: audit ownership lives here,
    at the application boundary surrounding the governed action - never
    inside ResearchAgent or ToolExecutor. Deliberately does not persist
    the raw query, prompt, model response, or Wikipedia content - only
    structured, technical metadata, now including the root execution_id/
    correlation_id so this row can be joined back to its ExecutionRecord
    (P7.16 §18) without adding new AuditLog columns."""
    details = json.dumps(
        {
            "tool_id": "wikipedia_search",
            "agent_id": agent.identity.agent_id,
            "permission": ToolPermission.NETWORK.value,
            "authorized": True,
            "executed": True,
            "success": success,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
        }
    )
    AuditLogRepository(db).create(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=_OPERATION,
            resource_type="tool_invocation",
            details=details,
        )
    )
