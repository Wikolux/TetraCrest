# Adding an Agent

There are two kinds of "new agent" in this platform: a new **specialist** (the common case — Learning, Product, Finance, Business Architect from the roadmap all fall here), and a new **top-level agent** like the Executive (rare — there is currently exactly one). This guide covers the specialist path in depth, since that's the platform's actual extension point, and notes the difference for the rarer case at the end.

## Prerequisite Reading

- [Specialist_Framework.md](../03_INTELLIGENCE/Specialist_Framework.md) — the architecture you're extending.
- [Research_Agent.md](../05_AGENTS/Research_Agent.md) — the first worked example; pattern-match against it.
- [Personal_Intelligence_Agent.md](../05_AGENTS/Personal_Intelligence_Agent.md) — a second worked example (CP-01, the first Capability Pack), useful specifically for a write-capable specialist (`remember()`-based operations) rather than Research's read-only pattern, and for the `AgentCapability` collision it deliberately avoids — see that doc's "Why No `AgentCapability.MEMORY`" section before deciding what capabilities your own specialist should declare.
- [Insight_Agent.md](../05_AGENTS/Insight_Agent.md) — a third worked example (CP-01.3), useful specifically for two things no other specialist demonstrates: (1) nesting a second, sibling specialist inside an existing pack's package (`personal_intelligence/insight/`) rather than creating a new top-level specialist package - see that doc's Dependency section for why this needed zero new `dependency_rules.py` boundary entry; (2) a pure, no-I/O detection/synthesis engine (`InsightEngine`) kept strictly separate from the agent orchestrating it, mirroring `ResearchSynthesizer`'s own "same input, same output" precedent - reach for this shape whenever your specialist's core logic must be independently, deterministically testable.

## Steps: Adding a New Specialist

1. **Define your specialist's own value objects, if needed.** `ResearchAgent` has `ResearchReport`; a Finance specialist might need a `FinanceAnalysis` type. These live in your specialist's own subpackage (`agents/specialists/finance/`, mirroring `agents/specialists/research/`), not in `agents/specialists/shared/`.

2. **Implement `SpecialistAgent`.**

```python
from app.services.ai.agents.specialists.specialist_agent import SpecialistAgent

class FinanceAgent(SpecialistAgent):
    def initialize(self) -> None: ...
    def execute(self, context, request) -> SpecialistResponse: ...
    # ... every other BaseAgent abstract method
```

Use the parametrized "missing any required member cannot be instantiated" test pattern (see [Testing.md](Testing.md)) to prove your implementation is complete before writing behavior tests.

3. **Decide whether you need a custom planner.** If your specialist's planning needs differ from a generic template, subclass `SpecialistPlanner` (see `ResearchPlanner` for the pattern). If not, the default is usable directly.

4. **Wire up adapters as needed.** If your specialist needs tools, hold a `ToolAdapter`. If it needs memory, hold a `MemoryAdapter`. If it needs to call the Runtime directly, hold a `RuntimeAdapter`. Don't import `ToolExecutor`/`MemoryRetrievalPipeline`/`AIRuntime` directly — the adapters exist specifically so your specialist depends on a small, fakeable seam. See [Specialist_Framework.md](../03_INTELLIGENCE/Specialist_Framework.md#adapters-why-they-exist).

5. **Apply your own execution policy.** Build a `SpecialistExecutionPolicy` and — critically — actually pass it into whatever `ToolExecutor` your specialist constructs. This is not automatic; `ResearchAgent`'s equivalent wiring was a real gap that had to be fixed explicitly. Verify your policy's `retry_policy`/`timeout_seconds` genuinely govern your tool calls with a test, not just by inspection.

6. **Define your own event type if your specialist's lifecycle doesn't fit `ResearchEventType`.** There is no generic `SpecialistEvent` base yet (see [Event_System.md](../02_KERNEL/Event_System.md)) — build `FinanceEvent`/`FinanceEventType` following `ResearchEvent`'s exact shape (subclass `GenericEvent`, restate `__hash__ = hash_event`).

7. **Register.**

```python
SpecialistRegistry.register(
    "finance",
    FinanceAgent,
    specialization="finance",
    supported_tasks={SpecialistTaskType.FINANCIAL_ANALYSIS},  # add new task types to SpecialistTaskType as needed
    overwrite=True,
)
AgentRegistry.register("finance", FinanceAgent, overwrite=True)
```

Registering in both `SpecialistRegistry` (for the Executive's `Dispatcher` to route to it) and `AgentRegistry` (for generic agent discovery) mirrors exactly what `ResearchAgent` does.

8. **Verify Executive routing end to end.** With your specialist registered and declaring the right `supported_tasks`, confirm `Dispatcher` actually routes a task with `metadata["required_capability"]` matching your specialist to it — don't assume registration alone wires this up; write the integration test.

9. **Test everything**, mirroring `test_research_agent.py`'s (or `app/tests/personal_intelligence/`'s) structure: ABC enforcement, registry registration/Open-Closed, planner behavior, adapter delegation (verify each adapter method is a one-line passthrough via `inspect.getsource`, matching the existing pattern), policy wiring, cancellation propagation, event ordering. If your specialist writes to memory (not just reads, like Research), also write an executive-integration test proving the Executive's own unmodified retrieval surfaces what you wrote — see `test_executive_integration.py` for the pattern.

## If You're Adding a New Top-Level Agent (Rare)

Follow the same shape as `ExecutiveAgent`, but implement `BaseAgent` directly (not `SpecialistAgent`), and register only in `AgentRegistry` — there is no reason to register a top-level agent in `SpecialistRegistry`. Think carefully before doing this: the platform currently has exactly one top-level agent by design, and most new capabilities belong in the Specialist layer, dispatched to by the existing Executive, rather than as a second top-level coordinator.

## Checklist

- [ ] Implements the full `SpecialistAgent`/`BaseAgent` contract (verified by an ABC-enforcement test)
- [ ] Uses adapters (`ToolAdapter`/`MemoryAdapter`/`RuntimeAdapter`), never the underlying subsystems directly
- [ ] Actually applies its own `SpecialistExecutionPolicy` where it builds a `ToolExecutor`
- [ ] Registered in `SpecialistRegistry` with accurate `specialization`/`supported_tasks`
- [ ] Registered in `AgentRegistry`
- [ ] Has its own event type if its lifecycle doesn't fit `ResearchEventType`
- [ ] No modification to `Dispatcher`, `SpecialistFactory`, `SpecialistCoordinator`, or `ExecutiveAgent` itself
- [ ] Full test suite: ABC enforcement, registry, planner, adapters, policy wiring, cancellation, events
