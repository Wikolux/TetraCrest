"""Core value objects for the Agent Framework.

Deliberately imports RuntimeResponse (app.services.ai.runtime.types) and
ExecutionMetrics/TokenUsageReference (app.services.ai.kernel.metrics) -
both are explicitly allowed dependencies ("AI Runtime", "Kernel
interfaces"), and reusing them here means an agent's execution result
composes the same normalized shapes the rest of the platform already
uses, instead of the Agent Framework re-inventing its own metrics/
response types.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.enums import AgentState
from app.services.ai.agents.events import AgentEvent
from app.services.ai.kernel.metrics import ExecutionMetrics
from app.services.ai.runtime.types import RuntimeResponse

Metadata = Mapping[str, Any]


class AgentError(Exception):
    """Root exception for the Agent Framework."""


class AgentPermissionError(AgentError):
    """Raised when an agent is not permitted to execute under the
    PermissionPolicy currently in effect."""


def _freeze_mapping(instance, field_name: str) -> None:
    value = getattr(instance, field_name)
    if not isinstance(value, MappingProxyType):
        object.__setattr__(instance, field_name, MappingProxyType(dict(value)))


@dataclass(frozen=True)
class AgentIdentity:
    """Immutable identity for one agent - never changes during execution.

    Deliberately excludes `state` despite it appearing in the milestone's
    example field list: identity is a fact about *what an agent is*,
    fixed at registration, while state is a fact about *what an agent is
    currently doing*, which necessarily changes as it runs. Conflating
    the two inside one frozen dataclass would either make state fake-
    immutable or make identity not genuinely immutable - state lives on
    AgentStateMachine (state.py) instead, which every agent instance owns
    separately from its identity.
    """

    agent_id: str
    name: str
    display_name: str
    description: str = ""
    version: str = "1.0"
    owner: str | None = None
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    permissions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AgentExecutionResult:
    """The outcome of one AgentExecutor.execute() call.

    response is the RuntimeResponse the agent's own execute() produced
    (None if the agent raised before ever reaching the runtime). error is
    populated on failure - state alone (FAILED) says *that* it failed,
    error says *why*, mirroring RuntimeResponse's own success/error split.

    execution_id/parent_execution_id/correlation_id/causation_id are
    copied directly from the AgentContext.shared that produced this
    result (via SharedExecutionContext.identity_fields(), never derived
    by inspecting `events`) - exactly the same four fields RuntimeResponse
    carries, so "which agent execution produced this" never requires
    walking events either. Defaults mirror RuntimeResponse's for the same
    reason: constructible without a context in tests, but AgentExecutor
    always supplies real ones from the context it ran.
    """

    agent_id: str
    state: AgentState
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    response: RuntimeResponse | None = None
    events: tuple[AgentEvent, ...] = field(default_factory=tuple)
    metrics: ExecutionMetrics | None = None
    error: str | None = None
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_execution_id: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_mapping(self, "metadata")

    @property
    def success(self) -> bool:
        return self.state not in (AgentState.FAILED, AgentState.CANCELLED)
