"""SpecialistCoordinator - holds the five collaborators every specialist's
own workflow needs (planner, memory adapter, tool adapter, runtime
adapter, synthesizer), wired via constructor injection. No business logic
lives here: this is a plain DI container/facade, not an orchestration
engine - each concrete specialist's own code (e.g. ResearchAgent.research())
decides *how* to sequence calls into these collaborators, since that
sequencing is exactly the domain-specific behavior that makes one
specialist different from another.

synthesizer is deliberately untyped (Any): synthesis output is
specialist-specific (a ResearchReport-oriented SynthesisResult today; a
different shape for a future Finance/Trading specialist), and the
Coordinator - a generic, specialist-agnostic piece of the framework - must
not import anything from a concrete specialist package like research/.
This mirrors app.services.ai.kernel.registry.RuntimeRegistry.register_capability_runtime(),
which holds `runtime: object` for the identical reason.

memory_adapter is typed as AgentMemory (M20.6), not the concrete
MemoryAdapter, for the same genericity reason: a specialist should depend
on the abstract memory contract, not one specific adapter implementation.
MemoryAdapter remains the only concrete AgentMemory today and is still
what every specialist actually constructs by default.
"""

from dataclasses import dataclass
from typing import Any

from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.specialists.planner import SpecialistPlanner
from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.agents.specialists.tool_adapter import ToolAdapter


@dataclass
class SpecialistCoordinator:
    planner: SpecialistPlanner
    memory_adapter: AgentMemory
    tool_adapter: ToolAdapter
    runtime_adapter: RuntimeAdapter
    synthesizer: Any = None
