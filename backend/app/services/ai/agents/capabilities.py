"""Agent capability declarations - what an agent supports, not what a
provider supports (see app.services.ai.shared.types.ProviderCapabilities
for that, unrelated concern).
"""

from dataclasses import dataclass, field

from app.services.ai.agents.enums import AgentCapability


@dataclass(frozen=True)
class AgentCapabilities:
    """The set of capabilities one agent declares it supports.

    declared is coerced to a real frozenset in __post_init__ regardless of
    what iterable was passed in (a list, a set, a generator, ...) - a
    frozen dataclass field holding a plain (mutable) set would still let a
    caller mutate that set in place, which frozen=True alone doesn't
    prevent.
    """

    declared: frozenset[AgentCapability] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.declared, frozenset):
            object.__setattr__(self, "declared", frozenset(self.declared))

    def has(self, capability: AgentCapability) -> bool:
        return capability in self.declared
