"""Dispatcher - matches a Task to a registered agent by capability.

Never a hardcoded `if "research" in query` branch: matching is done purely
by comparing the capability a Task declares it needs (task.metadata["required_capability"],
set by whatever planner created it) against BaseAgent.capabilities() of
every known candidate. Adding a new specialized agent therefore never
requires modifying this file - only registering the new agent (and its
capabilities) is needed, satisfying the Open/Closed requirement this
milestone tests directly.

Matching is deliberately per-*task*, not per-Decision: a Decision's
requires_memory/requires_tools/requires_web flags describe the *plan* as
a whole (real request-scoped policy questions - see
ExecutiveAgent.dispatch()'s allow_web/allow_tools gating, and
required_capabilities() below, which reads exactly those flags for that
purpose). Matching dispatch() itself against the whole Decision would
mean every task in a plan that "requires_memory" gets routed to a
memory-capable agent - including tasks that have nothing to do with
memory - the moment one is registered. Each task instead carries only the
one capability (if any) it specifically needs.

candidates is a mapping of already-constructed BaseAgent instances, not
AgentRegistry's own registered *classes*: capabilities() is an instance
method (a class alone can't answer "what does this support" without being
constructed, and agent constructors aren't standardized on one shape -
see AgentFactory.create()'s own *args/**kwargs). AgentRegistry/AgentFactory
remain how an agent's *class* gets discovered and instantiated; Dispatcher
only ever matches among instances the caller (the ExecutiveAgent) already
holds.
"""

from typing import Mapping

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.enums import AgentCapability
from app.services.ai.agents.executive.decision import Decision
from app.services.ai.agents.executive.task import Task

_FLAG_TO_CAPABILITY: dict[str, AgentCapability] = {
    "requires_memory": AgentCapability.MEMORY,
    "requires_tools": AgentCapability.TOOLS,
    "requires_web": AgentCapability.RESEARCH,
}


def required_capabilities(decision: Decision) -> frozenset[AgentCapability]:
    """The set of capabilities a Decision's boolean flags imply the overall
    plan needs - used for request-scoped policy questions (see
    ExecutiveAgent.dispatch()), not for matching any one task."""
    return frozenset(
        capability for flag, capability in _FLAG_TO_CAPABILITY.items() if getattr(decision, flag)
    )


class Dispatcher:
    def dispatch(
        self, decision: Decision, task: Task, candidates: Mapping[str, BaseAgent]
    ) -> BaseAgent | None:
        """Return the agent instance that should handle `task`, or None if
        no known candidate can - the caller (ExecutiveAgent) is expected
        to handle the task itself in that case.

        decision.selected_agent, when set, names an explicit override
        checked first (by name, in `candidates`) before falling back to
        matching task.metadata["required_capability"] - a task with no
        such tag needs no external agent at all (None, always).
        """
        if decision.selected_agent is not None:
            return candidates.get(decision.selected_agent)

        required = task.metadata.get("required_capability")
        if required is None:
            return None

        for agent in candidates.values():
            if required in agent.capabilities().declared:
                return agent
        return None
