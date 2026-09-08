"""The one authoritative seam for resolving "today" for Personal OS's own
API surface (P7.17).

Every Personal OS flow already requires its caller to supply `today: date`
explicitly (Phase 0's own finding: no flow anywhere in this package calls
`date.today()`/`datetime.now()` itself) - this module exists so the API
layer has exactly one place that decides what "today" means, rather than
each route computing it independently.

Current assumption, explicit and documented rather than implicit: "today"
is the current UTC calendar date, server-side. This is NOT user-timezone-
aware - a user whose local calendar day has not yet turned over relative
to UTC (or already has) will see Personal OS's "today" boundary at the
wrong wall-clock moment for them. This is a known, real limitation
(Phase 0's own §18 "timezone readiness: missing"), not solved here.

The seam is deliberately this narrow - a single function, no per-user
timezone profile, no timezone database - specifically so that a future
user-timezone-aware resolver can replace this function's own body alone
(e.g. reading a per-user timezone preference and converting) without any
caller anywhere in the API layer changing at all.
"""

from datetime import UTC, date, datetime


def resolve_personal_os_today() -> date:
    """The current Personal OS "today", per the UTC-calendar-date
    assumption documented above. Every mutating Personal OS route must
    call this itself, server-side, rather than accepting a client-
    supplied date for what "today" is."""
    return datetime.now(UTC).date()
