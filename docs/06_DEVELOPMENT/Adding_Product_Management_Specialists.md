# Adding a Product Management Specialist

This guide covers extending CP-02 specifically — either a new operation on one of the five existing specialists, or (rarer) a genuinely new sixth specialist. It assumes [Adding_Agent.md](Adding_Agent.md)'s general specialist-extension steps and narrows them to CP-02's own established conventions. Read [Product_Management_Intelligence.md](../04_CAPABILITIES/Product_Management_Intelligence.md) first for what the pack already guarantees — this guide is about extending it without breaking that.

## Prerequisite Reading

- [Adding_Agent.md](Adding_Agent.md) — the general specialist-extension steps this guide narrows.
- [Product_Management_Intelligence.md](../04_CAPABILITIES/Product_Management_Intelligence.md) — the pack's own capability guide; know its boundaries and evidence model before extending it.
- One existing specialist's own source as a worked example — `discovery/discovery_agent.py` for a read-heavy, evidence-gathering shape; `product_decision/product_decision_agent.py` for a framework-application shape; `stakeholder_communication/stakeholder_communication_agent.py` for the one specialist with a differentiated capability set (`COMMUNICATION`) and a hard "never sends" constraint.
- [ARR.md §6, §7](../08_CAPABILITY_PACKS/CP-02_Product_Management_Intelligence_Pack/ARR.md) — the memory-lifecycle and evidence-traceability conventions every specialist must follow, resolved into [Architecture.md §21](../08_CAPABILITY_PACKS/CP-02_Product_Management_Intelligence_Pack/Architecture.md).

## First: Do You Need a New Specialist at All?

CP-02's own history argues against it. Two capabilities the PRD names as if they were dedicated specialists — Portfolio Intelligence (PRD §19) and Career Development (PRD §20) — were deliberately folded into an existing specialist instead (a dormant, honestly-scoped operation on Strategy & Portfolio; a byproduct memory write from Product Decision). Before proposing a sixth specialist, check:

- Does this capability need its own state machine, event vocabulary, and memory ownership — or can it be a new operation on a specialist that already owns the adjacent memory category?
- Does it introduce a genuinely new professional-practice responsibility (PRD §15–§20 named five), or is it a variation on one that already exists?

A new operation on an existing specialist is Implementation Plan work at the operation level — no dependency-boundary change, no new registry entry, no new Architecture Readiness Review. A new specialist is a Phase 2 (Architecture) decision, reviewed with the same rigor CP-02's own ARR applied, never introduced unilaterally inside an implementation milestone.

## Adding a New Operation to an Existing Specialist

1. **Add the operation to that specialist's own `*Operation` `StrEnum`** (`request.py`), never a shared, cross-specialist operation type — each specialist's operation vocabulary is deliberately its own (`DiscoveryOperation`, `DecisionOperation`, `DeliveryOperation`, `StrategyOperation`, `StakeholderCommunicationOperation`).
2. **Decide whether the operation writes to memory.** If it produces a durable fact, it must write through that specialist's own `ProfessionalMemoryService` method (adding a new `remember_*()` there if needed) into an *already-approved* `product_*` memory category (`shared/types.py`'s `ALL_MEMORY_TYPES`) — never a new category invented for one operation. See ADR-0006: a business concept does not automatically warrant its own `memory_type`.
3. **If the operation writes a domain object that makes a claim** (a finding, a decision, a recommendation with cited evidence), enforce evidence structurally, not conventionally: a required-evidence field validated in `__post_init__`, mirroring `DiscoveryFinding`/`ResearchFinding`/`DecisionRecord`'s existing pattern (ARR §7). Do not add a field that's merely documented as "should be populated" — if it's required, the object must not be constructible without it.
4. **If the operation can fail to have enough evidence, it must fail honestly.** Return a low-confidence `SpecialistResponse` stating the evidence gap explicitly; do not write a partial or inferred record. This is not optional per-operation judgment — it is the pack-wide rule every existing operation already follows (ARR §8, Failure Mode Analysis).
5. **Add the corresponding event member** to that specialist's own `*EventType` (never a new event mechanism — `GenericEvent`/`EventPublisher`, unmodified).
6. **Add the operation to the specialist's own dispatch table** (`self._operations: dict[Operation, Callable]`, the pattern every specialist already uses) and add the routing test proving `process()` reaches your new handler.
7. **Test it exactly like an existing operation is tested**: happy path with evidence, honest failure without evidence, event emission, memory write (or explicit absence, if the operation is read-only), and — if the operation constructs a new domain object — the ABC/`__post_init__` construction-failure test proving the required field truly is required.

## Adding a Genuinely New (Sixth) Specialist

Follow [Adding_Agent.md](Adding_Agent.md)'s full specialist-creation steps, plus these CP-02-specific requirements:

### Required Architecture

- Package lives at `agents/specialists/product_management/<name>/`, a sibling of the five existing specialist packages — this inherits the single, already-registered `agents.specialists.product_management` dependency-boundary entry automatically (longest-prefix match). Do not register a new, more specific boundary entry unless the new specialist's own dependency needs genuinely differ from the existing allow-set (`agents.specialists`, `agents`, `tools`, `shared`, `runtime`, `kernel`, `providers`) — none of the five existing specialists has ever needed one.
- Own `shared/` types only if the new specialist introduces domain objects no existing specialist needs — reuse `shared/types.py`'s memory-type constants and any existing domain object (`Product`, `Stakeholder`, etc.) rather than redefining an equivalent.
- Declare `AgentCapability.REASONING`/`PLANNING` at minimum, matching every existing specialist; add `COMMUNICATION` only if the specialist genuinely drafts communication (Stakeholder Communication's own precedent). **Never declare `AgentCapability.MEMORY`** — this is not a style preference, it is what keeps `Dispatcher` from routing the Executive's own internal `retrieve_memory`/`retrieve_conversations` tasks to your specialist, which would break the Executive's generic flow.

### Required Memory Discipline

- Every new memory category must be added to `shared/types.py`'s `ALL_MEMORY_TYPES`, namespaced `product_*`, with a single named owner — before writing this checklist item off, re-read ADR-0006 and confirm the concept genuinely needs different retrieval, ownership, retention, or reasoning treatment from all ten existing categories, not merely a different name.
- Every write goes through `AgentMemory.remember()` (via that specialist's own `ProfessionalMemoryService` method), every read through `AgentMemory.retrieve()`/`.search()` — never a second memory mechanism, never a direct `AIMemoryService`/`AIRuntime` construction inside the specialist (verified pack-wide by Milestone 8's `test_no_specialist_module_constructs_airuntime_or_aimemoryservice_directly`).
- Follow the append-only convention uniformly: an update is a new memory entry referencing the prior state, never an in-place edit; deletion is user-requested only, via `AgentMemory.forget()`.

### Required Evidence Discipline

- Any domain object that makes a claim (a finding, a recommendation, a decision) must structurally require its supporting evidence at construction — the `__post_init__` pattern every existing CP-02 domain object uses, tracing to CP-01.3's `Insight.supporting_memory_ids` precedent.
- Confidence must reflect evidence quality — depressed, never inflated, when evidence is thin.
- Never write a record claiming validation, decision, or completion that the retrieved evidence doesn't actually support.

### Required Event Discipline

- Define `<Name>EventType`/`<Name>Event`, subclassing `GenericEvent` exactly as every existing CP-02 specialist's own event module does (`__hash__ = hash_event` restated, matching the platform-wide convention) — there is still no generic `SpecialistEvent` base to subclass instead.
- Emit `REQUEST_STARTED`/`REQUEST_COMPLETED`/`REQUEST_FAILED` at minimum, plus one member per operation-specific milestone (a write, a recall completion) — mirror an existing specialist's event vocabulary for the shape, not the literal names.

### Required Testing Discipline

Mirror an existing specialist's own test file structure (e.g., `test_discovery_agent.py`), plus the pack-wide suites a new specialist must be added to:

- ABC/registry conformance, planner behavior, adapter delegation, policy wiring, cancellation, event ordering — the same checklist [Adding_Agent.md](Adding_Agent.md) already requires of every specialist.
- Every operation: happy path with evidence, honest failure without evidence, the exact memory write (or its absence) the operation should produce.
- Add the new specialist to `_SPECIALIST_MODULES`/`_SPECIALIST_FACTORIES`-shaped dicts in the pack-wide Milestone 8 suites (`test_product_management_executive_integration.py`, `test_product_management_workflow_integration.py`, `test_product_management_architecture_integration.py`) so the pack-wide proofs — zero specialist-to-specialist imports, zero `MEMORY` capability declarations, zero direct `AIRuntime`/`AIMemoryService` construction, Dispatcher routing correctness — cover it automatically rather than needing a parallel, hand-maintained sixth suite.
- If the new specialist consumes another CP-02 specialist's output, add an end-to-end workflow test proving the handoff happens through shared memory only — never assert on the producing specialist's internal state or types.

## Checklist

- [ ] Every field [Adding_Agent.md](Adding_Agent.md)'s own checklist already requires
- [ ] New memory categories (if any) are genuinely new by ADR-0006's test, added to `ALL_MEMORY_TYPES`, `product_*` namespaced, single owner
- [ ] No new dependency-boundary entry unless the allow-set genuinely differs from the existing pack-wide one
- [ ] Declares `REASONING`/`PLANNING` (+ `COMMUNICATION` only if genuinely drafting), never `MEMORY`
- [ ] Every evidence-bearing domain object enforces its evidence structurally (`__post_init__`), not conventionally
- [ ] Every operation fails honestly (explicit evidence gap, low confidence, no fabricated write) when evidence is insufficient
- [ ] Never imports another CP-02 specialist's code, `ResearchAgent`'s implementation, or CP-01's code
- [ ] Added to the pack-wide Milestone 8 test suites, not just its own standalone test file
