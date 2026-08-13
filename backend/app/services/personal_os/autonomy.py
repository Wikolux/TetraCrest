"""Context-dependent autonomy policy (P5 §18-§21): a pure permission
check, never an execution engine - this module answers "is this action
currently authorized for this mission?" and nothing else. There is no
code anywhere in this package that reserves a flight, sends an
application, posts to LinkedIn, or moves money; per §24's own integration
boundary, no such surface exists yet. is_authorized() is the seam a
future integration would call before attempting a consequential action -
building it now, without anything on the other end of it yet, is
deliberate: the policy the spec describes needs to be a genuine
architectural constraint from day one, not bolted onto whatever
integration ships first.

Governing precedent: PRODUCT_PHILOSOPHY_FREEZE_v1.md §5 - "Human
override. A person's own judgment always outranks the platform's...
AI that acts irreversibly without explicit human approval. Consequential,
unrecoverable action is never taken on a person's behalf without them
deliberately saying yes first." REQUIRES_EXPLICIT_AUTHORIZATION below is
this module's own concrete enforcement of that platform-wide,
second-highest-authority commitment - RESERVE/EXECUTE are exactly the
"consequential, unrecoverable" tier that commitment names, and neither
one is ever granted by default, regardless of mission or context.
"""

from datetime import UTC, datetime

from app.services.personal_os.mission import AutonomyGrant
from app.services.personal_os.shared.types import AutonomyAction

# OBSERVE/RESEARCH/PREPARE/RECOMMEND/ASK are reversible, non-consequential
# on their own (looking things up, drafting, asking a question) and are
# allowed without an explicit grant. RESERVE/EXECUTE are the two levels
# with a real financial/reputational/employment/legal consequence (§18's
# own list) and always require one - never inferred, never generalized
# from a prior grant for a different action or a different mission (§20).
REQUIRES_EXPLICIT_AUTHORIZATION: frozenset[AutonomyAction] = frozenset({AutonomyAction.RESERVE, AutonomyAction.EXECUTE})


def is_authorized(grants: tuple[AutonomyGrant, ...], *, action: AutonomyAction, now: datetime | None = None) -> bool:
    """True only if `grants` contains a grant for exactly this action
    that is neither revoked nor expired (§20). Actions outside
    REQUIRES_EXPLICIT_AUTHORIZATION are always True - they need no grant
    at all. This function never looks at scope text beyond confirming it
    is non-empty (AutonomyGrant.__post_init__ already enforces that) -
    matching a grant's own stated scope against a specific real-world
    action is a judgment call for whatever future integration actually
    attempts the action, not something this deterministic gate decides;
    this gate only answers "has the user said yes to this ACTION on this
    MISSION at all," the minimum, unambiguous check every stricter,
    scope-aware check must still pass first."""
    if action not in REQUIRES_EXPLICIT_AUTHORIZATION:
        return True

    moment = now or datetime.now(UTC)
    for grant in grants:
        if grant.action != action:
            continue
        if grant.revoked:
            continue
        if grant.expires_at is not None and grant.expires_at <= moment:
            continue
        return True
    return False


def active_grants(grants: tuple[AutonomyGrant, ...], *, now: datetime | None = None) -> tuple[AutonomyGrant, ...]:
    """Every grant currently in force (not revoked, not expired) -
    useful for surfacing "what am I currently authorized to do on this
    mission" without re-deriving the revocation/expiry check inline
    everywhere it is needed."""
    moment = now or datetime.now(UTC)
    return tuple(g for g in grants if not g.revoked and (g.expires_at is None or g.expires_at > moment))
