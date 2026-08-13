# CP-02 — Product Management Intelligence Pack
## Implementation Plan (Phase 3)

| | |
|---|---|
| **Status** | Draft — Phase 3 (Implementation Plan), per [VERSION_1_DEVELOPMENT_GUIDE.md](../../VERSION_1_DEVELOPMENT_GUIDE.md) §4 |
| **Built from** | [PRD.md](PRD.md) (Phase 1, approved), [Architecture.md](Architecture.md) (Phase 2, approved), [ARR.md](ARR.md) (Phase 2.5, verdict: READY WITH CONDITIONS) |
| **Governed by** | [MASTER_BLUEPRINT.md](../../MASTER_BLUEPRINT.md), [PRODUCT_PHILOSOPHY_FREEZE_v1.md](../../PRODUCT_PHILOSOPHY_FREEZE_v1.md), [ARCHITECTURE_FREEZE_v1.md](../../ARCHITECTURE_FREEZE_v1.md), [VERSION_1.0_MILESTONE_ZERO.md](../../VERSION_1.0_MILESTONE_ZERO.md), [VERSION_1_DEVELOPMENT_GUIDE.md](../../VERSION_1_DEVELOPMENT_GUIDE.md) |
| **Precedes** | Phase 4 — Implementation (Production Code) |
| **Modifies** | Nothing above. This document is purely additive: no frozen interface, no governance document, and no part of CP-01 is touched or proposed for change anywhere below. |

This document contains no code, no package structure, no class hierarchy, no API design, and no pseudocode. It is the Phase 3 deliverable the [Version 1 Development Guide](../../VERSION_1_DEVELOPMENT_GUIDE.md) §4 defines: a concrete, sequenced plan for *how* the already-approved CP-02 Architecture gets built, so that Phase 4 is execution against a settled plan, not further design. Every recommendation below traces to a specific section of the PRD, the Architecture, or the ARR — never to a new decision made for the first time in this document.

---

## 1. Purpose

Phase 2 produced an approved architecture. Phase 2.5 independently verified that architecture was sound, complete, and implementable. Neither phase, by design, decided *in what order* CP-02 gets built, *what a developer needs in hand* before writing the first line of it, or *how progress gets checked* along the way. That is this document's entire job.

This is the bridge between Architecture and Production. An architecture document describes a destination — five specialists, a professional memory model, a defined integration boundary with CP-01. An implementation plan describes the route: which piece is built first, what it depends on, how each piece is proven correct before the next is layered on top of it, and what conditions must hold before the whole pack is considered ready to ship. Where the Architecture answers "what is CP-02," this document answers "in what order, and by what discipline, does CP-02 come into existence."

Nothing below authorizes a design decision the Architecture did not already make. Where this document is specific about sequencing, testing, or risk, it is translating an already-approved design into an executable plan — never quietly deciding something Phase 2 or Phase 2.5 left open. Where a genuine open question remains (there is one, inherited directly from Architecture §9 and ARR §5.2, and revisited honestly in §10 below), this document says so rather than resolving it by assumption.

## 2. Implementation Scope

### Will be implemented (Phase 4)

- **Shared domain models** for every entity named in Architecture §7 (Product, Feature/Initiative, Roadmap Item, Metric, Discovery Finding/Hypothesis, Research Finding, Stakeholder, Decision Record, Portfolio).
- **Professional Memory**, realized through the ten memory categories named in Architecture §6, written and read entirely through the existing `AgentMemory` surface.
- **Five specialists**, each at the scope Architecture §3 and PRD §25 assign them for v1/v2: **Discovery**, **Delivery**, **Product Decision** (Decision Support and Prioritization only — not the Career Development maturity assigned to v3), **Strategy & Portfolio** (single-product Strategy only — not the full cross-product Portfolio Intelligence maturity assigned to v3), and **Stakeholder Communication** (v2-scoped per the PRD, built as part of this same implementation arc since its architecture is already fully specified).
- **Executive integration** for all five specialists, via the existing capability-based `Dispatcher` mechanism, unmodified.
- **Research integration**, limited to the sequential delegation shape Architecture §9 already specifies as sufficient for v1/v2 (§10 below).
- **Read-only integration with CP-01**, exactly as Architecture §19 specifies, for identity, voice, and goal context.
- **The dependency-boundary registration** CP-02's own code will require (ARR §13, revisited precisely in §15 below).
- **Full documentation** — capability-level, agent-level, and the governance-tracker updates the Development Guide requires at every milestone.

### Deliberately excluded from this Implementation Plan

- **An AI Product Management synthesis specialist.** None is being built, in any phase — Architecture §10 established this permanently as an Executive-level pattern, not a component. There is nothing for Phase 4 to build here.
- **A dedicated Research specialist.** CP-02 never builds its own research capability; it only frames questions for the existing `ResearchAgent` (§10 below). Nothing new is implemented for this beyond the framing/recording behavior already inside the Discovery and Strategy & Portfolio specialists.
- **Full, cross-product Portfolio Intelligence.** The Strategy & Portfolio Specialist is built with this as a ready, architecturally anticipated extension (Architecture §12), not as working v1/v2 functionality.
- **Career Development as a realized capability.** The Product Decision Specialist is built without its Career Development reasoning mode; that mode is v3 scope, per the PRD's own phasing.
- **Vision-assisted discovery capture.** Blocked, platform-wide, on a concrete Vision provider that does not yet exist anywhere on the platform (§13).
- **Any concrete Tool Framework integration** (issue trackers, calendar/roadmap tools). Blocked, platform-wide, on a concrete tool that does not yet exist (§12).
- **Single-plan, multi-specialist Research delegation** (Architecture §9, shape 2). Remains an optional, unbuilt enhancement, not a Phase 4 deliverable (§10).

## 3. Implementation Strategy

**Implementation is incremental because the Architecture itself is incremental.** Architecture §3's Decision Table assigns each of CP-02's five specialists a distinct, self-contained unit of work with a named, narrow dependency shape on the others (§5, below). Building all five simultaneously would mean discovering integration problems only once every piece already existed — the most expensive point at which to discover them. Building them one at a time, each fully tested and verified before the next begins, means a defect is always caught against a small, well-understood surface, exactly the discipline CP-01 already proved out across its own four real phases.

**Every specialist is independently deployable because Architecture already guaranteed zero specialist-to-specialist coupling.** No CP-02 specialist reads another CP-02 specialist's internals — only shared Professional Memory (Milestone 2) and, read-only, CP-01's memory (Architecture §19). This means Discovery (Milestone 3) can be built, tested, and — in principle — released on its own, with Delivery, Product Decision, Strategy & Portfolio, and Stakeholder Communication arriving later without ever requiring Discovery to be revisited. Independent deployability is not an aspiration this plan hopes for; it is a direct, structural consequence of a design decision Architecture §3 already made.

## 4. Delivery Roadmap

The PRD's own illustrative milestone sequence named nine milestones but did not include a milestone for the Delivery Specialist — one of the five specialists Architecture §3 names as a full peer of Discovery, Product Decision, Strategy & Portfolio, and Stakeholder Communication, and one this plan's own §8 (Specialist Rollout Plan) is required to sequence. This plan corrects that omission explicitly, rather than either silently dropping Delivery or silently contradicting the Architecture's own specialist set: the roadmap below has **ten** milestones, with Delivery inserted at Milestone 5, immediately after Product Decision, for the dependency reasons explained in §5.

### Milestone 1 — Shared Domain Models

- **Objectives**: Establish the conceptual domain objects every later milestone reads and writes — the shared vocabulary Architecture §7 already names, given concrete form as the platform's own domain-object pattern (the same "frozen value object with a natural-language rendering" discipline CP-01's domain objects already established).
- **Dependencies**: None beyond the frozen platform and CP-01's memory (read-only).
- **Deliverables**: A domain object for each entity in Architecture §7 (§6, below); the `product_*` memory-type namespacing convention (Architecture §6); structural evidence-enforcement on the Decision Record object, closing ARR §7's own carried-forward finding at the earliest point it can be closed.
- **Acceptance criteria**: Every entity named in Architecture §7 has a corresponding domain object. A Decision Record cannot be constructed without a reference to the evidence and framework that produced it — verified by test, not by convention alone. Zero frozen interface touched.

### Milestone 2 — Professional Memory

- **Objectives**: Build the memory-service layer every specialist will depend on — the write path (`AgentMemory.remember()`) and the two read paths Architecture §5 specifies (semantic recall via `MemoryRetrievalPipeline`, and bulk/professional-context reads following the precedent CP-01.3's Insight Engine already established for its own bulk corpus needs).
- **Dependencies**: Milestone 1 (a memory write needs a domain object's rendered content to write).
- **Deliverables**: A working read/write path for every one of the ten memory categories named in Architecture §6; the corrected, structurally-consistent update/deletion convention ARR §6 specifies (append-only, mirroring CP-01's own `GoalProgressUpdate` precedent).
- **Acceptance criteria**: Every category in Architecture §6 has a proven write and a proven read path. No new memory storage, schema, or table exists anywhere in the deliverable — every category is a categorization convention on the existing `Memory` entity, exactly as Architecture §5 requires.

### Milestone 3 — Discovery Specialist

- **Objectives**: The first specialist. Built first because it has no dependency on any other CP-02 specialist's output (Architecture §3), and because its output — Discovery Findings — is the evidence foundation Product Decision and Delivery both need later.
- **Dependencies**: Milestone 1, Milestone 2.
- **Deliverables**: The Discovery Specialist, registered and capability-dispatchable, implementing problem validation, Jobs-to-be-Done framing, and hypothesis tracking (PRD §15); the platform's first dependency-boundary registration for CP-02 (§15, below — the earliest point at which one is actually possible).
- **Acceptance criteria**: Registered in the platform's specialist registries; declares no `AgentCapability.MEMORY` (Architecture §19); full test coverage per §14; zero regressions against the platform's existing suite.

### Milestone 4 — Product Decision Specialist

- **Objectives**: The second specialist, built next specifically because Decision Support is the capability ARR §7 identified as needing the platform's strongest evidence-traceability guarantee, and because later specialists (Strategy's prioritization, Stakeholder Communication's justification narratives) both reference decisions as precedent.
- **Dependencies**: Milestone 1, 2, 3 (reads Discovery Findings as evidence).
- **Deliverables**: The Product Decision Specialist, implementing framework selection and application (RICE, ICE, Kano, Cost of Delay, build-vs-buy, sunset checklist — Architecture §8) and the mandatory counterpoint step; the PM Craft Record byproduct write (Architecture §6, feeding the later, v3-scoped Career Development mode without needing to be revisited when that mode is eventually built).
- **Acceptance criteria**: Every recommendation carries a named framework and at least one surfaced counterpoint, verified by test (ARR §14's own quality rubric); Decision Records produced in practice satisfy Milestone 1's structural evidence requirement; zero regressions.

### Milestone 5 — Delivery Specialist

- **Objectives**: The third specialist, sequenced here — after Discovery and Product Decision, rather than earlier — because Delivery's own responsibility (PRD §16) is to turn already-validated, already-decided work into drafted artifacts; building it before evidence and decisions exist to draft against would leave it with nothing real to be tested against.
- **Dependencies**: Milestone 1, 2, 3, 4 (reads Discovery Findings and Decision Records for traceability).
- **Deliverables**: The Delivery Specialist, implementing PRD/spec drafting, user-story structuring, acceptance criteria, RACI structuring, and launch-readiness checks (PRD §16).
- **Acceptance criteria**: A drafted artifact is never produced without a traceable link to the Discovery Finding or Decision Record that grounds it (Architecture §14's own anti-pattern is verified absent by test); zero regressions.

### Milestone 6 — Strategy & Portfolio Specialist

- **Objectives**: The fourth specialist, built at single-product scope only (Architecture §12), with cross-product Portfolio reasoning built as a ready, dormant extension rather than working functionality.
- **Dependencies**: Milestone 1, 2, 4 (reads Decision Records as prioritization precedent).
- **Deliverables**: The Strategy & Portfolio Specialist, implementing roadmap sequencing, prioritization-framework application at the backlog level, and OKR/North Star Metric structuring (PRD §17); the Roadmap State and Metric memory categories exercised in practice.
- **Acceptance criteria**: A sequenced roadmap output names its tradeoffs explicitly; portfolio-grain (cross-product) reasoning is verifiably not attempted in this milestone's scope; zero regressions.

### Milestone 7 — Stakeholder Communication Specialist

- **Objectives**: The fifth and final specialist, built last among the five because it drafts communication about the other four specialists' own output — building it earlier would mean testing it against content that does not yet exist.
- **Dependencies**: Milestone 1, 2, 3, 4, 5, 6 (reads Product Knowledge state produced by every prior specialist milestone, and CP-01 identity for voice).
- **Deliverables**: The Stakeholder Communication Specialist, implementing stakeholder mapping (RACI), status/executive-summary drafting, and alignment narratives (PRD §18); Stakeholder Record memory category exercised.
- **Acceptance criteria**: No draft is produced without grounding in actual Product Knowledge state (Architecture §14's own anti-pattern verified absent); nothing is ever sent autonomously — verified by the absence of any send/publish capability, not merely by policy; zero regressions.

### Milestone 8 — Executive Integration

- **Objectives**: Prove, with real integration tests rather than description, that all five specialists integrate correctly with `ExecutiveAgent` — both the automatic path (content surfacing via shared memory, with zero delegation) and the explicit delegation path.
- **Dependencies**: Milestones 3 through 7 (every specialist must exist to be integration-tested).
- **Deliverables**: Executive-integration test coverage for all five specialists, including the collision-avoidance proof Architecture §19 requires (no CP-02 specialist ever intercepts the Executive's own internal memory-retrieval tasks).
- **Acceptance criteria**: Every specialist is proven capability-dispatchable; every specialist is proven to never declare `AgentCapability.MEMORY`; the full cross-pack proof pattern CP-01.3 established (a fact written by one component, surfaced automatically by a component with zero awareness of the first) is demonstrated for at least one CP-02 specialist reading CP-01 content.

### Milestone 9 — Documentation

- **Objectives**: Bring CP-02's documentation to the same completeness and accuracy standard CP-01's own documentation was held to, reflecting what was actually built rather than what was originally planned.
- **Dependencies**: Milestones 1 through 8 (documentation describes what exists).
- **Deliverables**: A capability-level document (mirroring `Personal_Intelligence_Pack.md`), five agent-level documents (mirroring `Personal_Intelligence_Agent.md`/`Insight_Agent.md`), the Architecture.md addendum ARR §15 condition 1 requires, and updated `Roadmap.md`/`Capability_Strategy.md` entries (§15, below).
- **Acceptance criteria**: Every cross-reference resolves; every document describes CP-02's actual, shipped state; ARR §15's first condition (folding the Review's corrections back into the canonical Architecture) is resolved, not merely acknowledged.

### Milestone 10 — Release Candidate

- **Objectives**: Assemble every deliverable from Milestones 1 through 9 into a single, complete, frozen candidate for release, with every checklist in the Development Guide passed.
- **Dependencies**: Milestones 1 through 9, complete.
- **Deliverables**: Release notes; a completion summary (Development Guide §5); confirmation that every ARR §15 condition has been resolved; a final, full run of the platform's test suite with zero regressions.
- **Acceptance criteria**: Every item in this plan's own §19 (Release Readiness) holds simultaneously.

## 5. Implementation Order

The order above is not arbitrary — each milestone depends on the previous ones for a specific, named reason, and the chain does not permit reordering without breaking a real dependency:

- **Milestone 2 depends on Milestone 1** because a memory write needs a domain object to render as content; there is nothing to remember until something exists to describe what is being remembered.
- **Milestone 3 (Discovery) depends on Milestones 1–2** because a specialist needs both the domain vocabulary and a working memory path before it can do anything durable.
- **Milestone 4 (Product Decision) depends on Milestone 3** because Decision Support's precedent-and-evidence discipline (Architecture §8) requires Discovery Findings to exist as evidence to reason over.
- **Milestone 5 (Delivery) depends on Milestones 3–4** because Delivery drafts artifacts *from* discovery evidence and decisions — building it before either exists would leave nothing real to draft.
- **Milestone 6 (Strategy & Portfolio) depends on Milestone 4** because prioritization work references Decision Records as precedent (Architecture §8/§12's own stated relationship).
- **Milestone 7 (Stakeholder Communication) depends on Milestones 3–6** because it communicates *about* what the other four specialists have already produced — it is architecturally incapable of being tested meaningfully before they exist.
- **Milestone 8 (Executive Integration) depends on Milestones 3–7** because integration testing requires every specialist it is testing to already exist.
- **Milestone 9 (Documentation) depends on Milestone 8** because documentation describes a working, integration-proven system, not a plan for one.
- **Milestone 10 (Release Candidate) depends on Milestone 9** because a release candidate is the assembled, complete result of every prior milestone, not a parallel effort.

No milestone in this chain can begin before the one it depends on has passed its own Implementation Gate (§17).

## 6. Domain Models

Every entity named in Architecture §7 requires a corresponding domain model. Each is described here by responsibility only — no fields, no types, no class design, consistent with this document's own constraints.

| Domain model | Responsibility |
|---|---|
| **Product** | Represents something the user is responsible for delivering value through; the anchor every other CP-02 entity is ultimately traced back to. |
| **Feature / Initiative** | Represents a discrete unit of product work under consideration or in flight; carries its own lifecycle stage and its links to the evidence that grounds it. |
| **Roadmap Item** | Represents a sequenced commitment or intention; carries its horizon and its dependency relationships to other roadmap items, potentially across Products. |
| **Metric** | Represents a quantitative signal the user tracks, including a Product's North Star Metric where one is defined. |
| **Discovery Finding / Hypothesis** | Represents evidence gathered from users, market, or competitors, and its current validation status; the evidentiary backbone every later recommendation traces to. |
| **Research Finding** | Represents the synthesized output of a delegated research question (§10); always carries a reference to the question that produced it. |
| **Stakeholder** | Represents a professional role or interest relevant to a product's decisions or communication — structurally distinct from any CP-01 personal relationship (§11). |
| **Decision Record** | Represents a structured product decision: the options considered, the framework applied, the rationale, and — once known — the outcome. Cannot be constructed without its supporting evidence references (Milestone 1). |
| **Portfolio** | Represents the user's own set of Products considered together; the frame the Strategy & Portfolio Specialist's cross-product reasoning operates over, once that reasoning matures beyond v1/v2 scope. |

## 7. Professional Memory Plan

The PRD's own phrasing for this section names six categories of professional understanding. Five map directly onto categories Architecture §6 already approved; the sixth does not correspond to a separately-approved category, and this plan does not introduce one silently:

- **Professional memories** — the Professional Memory Model as a whole (Architecture §6): all ten categories, described in full there and not restated here.
- **Decision memories** — the **Decision Record** category.
- **Research references** — the **Research Finding** category.
- **Meeting history** — **not a separately approved memory category.** Meeting- and interaction-relevant content is already covered by the **Stakeholder Record** category (interaction context with a specific stakeholder) and the **Delivery Artifact** category (drafted communication, including meeting-adjacent material such as agendas or talking points). Introducing an eleventh category for this would be exactly the kind of scope drift §16 (Risk Assessment) identifies as a risk this plan is designed to prevent — so this plan maps the need onto the two categories that already cover it, rather than inventing a new one.
- **Stakeholder knowledge** — the **Stakeholder Record** category.
- **Portfolio history** — the **Roadmap State** category, which Architecture §12 already establishes as sharing an owner with Portfolio-level state; no separate category is introduced.

**Reuse of the existing Memory Framework**: every category above is written through `AgentMemory.remember()` and read through `AgentMemory.retrieve()`/`.search()`, exactly as CP-01's own memory categories are — no new storage mechanism, no new schema, no new retrieval code path (Architecture §5). Retrieval remains semantic, not type-filtered, at the platform level; where a specialist genuinely needs a bulk, category-scoped view, it follows the exact precedent CP-01.3's Insight Engine already established for its own bulk corpus-gathering need, reusing the platform's existing bulk-listing capability rather than asking the Memory Framework for a filtered query it does not support.

## 8. Specialist Rollout Plan

The implementation sequence for the five specialists is: **Discovery → Product Decision → Delivery → Strategy & Portfolio → Stakeholder Communication** (Milestones 3 through 7).

This order minimizes risk in three specific ways. First, it builds the specialist with **zero dependency on any other CP-02 specialist first** (Discovery), so the earliest real integration work happens against the smallest possible surface — the shared foundation (Milestones 1–2) and CP-01, never another still-unbuilt CP-02 specialist. Second, it resolves the **highest-uncertainty capability early**: Product Decision Support carries the ARR's own strongest structural requirement (evidence-traceability), and building it second means that requirement is proven correct while the surrounding system is still small and any needed correction is cheap. Third, it builds **communication last**, deliberately, because Stakeholder Communication's entire job is to describe what the rest of the system has already produced — testing it against real, already-validated content (rather than placeholder content invented for the purpose) is both more realistic and structurally impossible to do any earlier.

## 9. Executive Integration Plan

CP-02 integrates with `ExecutiveAgent` exactly as Architecture §4 specifies, and this plan authorizes no deviation from it. Each of the five specialists self-registers into the platform's `AgentRegistry` and `SpecialistRegistry` at import time — the same convention every existing specialist already follows. Separately, whatever composes a running `ExecutiveAgent` for real use must include each constructed CP-02 specialist instance in its `known_agents` mapping — the same two-step requirement CP-01's and `ResearchAgent`'s own integration already has, restated here as a Milestone 8 deliverable, not a new requirement.

No modification to `ExecutiveAgent`, `ExecutivePlanner`, or `Dispatcher` is planned, proposed, or required anywhere in this plan. Delegation is reached entirely through the existing capability-matching mechanism: each specialist declares the `AgentCapability` values it genuinely has (`REASONING`, `PLANNING`, and — for Stakeholder Communication — `COMMUNICATION`), and never `MEMORY` (Architecture §19), so that the Executive's own built-in memory-retrieval tasks are never at risk of being intercepted by a CP-02 specialist. Milestone 8 is where this is proven by test, not merely asserted by design.

## 10. Research Integration

CP-02 reuses `ResearchAgent` exactly as Architecture §9 specifies, and this plan builds against only the shape Architecture §9 and ARR §5.2 already identified as sufficient and proven: **sequential delegation.** A research question is framed by the Discovery or Strategy & Portfolio Specialist and dispatched as its own top-level request, handled entirely by the existing `ResearchAgent` (already declaring `AgentCapability.RESEARCH`, already matched by `Dispatcher` without any change); the resulting findings are then given back to a CP-02 specialist in a later request, which records them as a Research Finding (§6, §7).

**No research functionality is duplicated anywhere in this plan.** CP-02 never performs source retrieval, evidence-gathering, or research synthesis itself — that capability remains entirely `ResearchAgent`'s, reused, never re-implemented.

Architecture §9's second, more ambitious shape — a single Executive plan delegating to a CP-02 specialist and `ResearchAgent` as sibling tasks within one `TaskGraph` — remains architecturally possible but is **not built in this plan**, consistent with Architecture §20's and ARR §5.2's own conclusion that it is a strict, optional enhancement to the Executive Framework's own planning template, not a CP-02 deliverable. If it is ever built, it is built as an Executive Framework improvement, reviewed with that framework's own rigor — never as a CP-02-private workaround.

## 11. Personal Intelligence Integration

CP-02 consumes CP-01 exactly as Architecture §19 specifies, and this plan reiterates the mechanism precisely because it is the single most important boundary this implementation must never cross:

- **No direct imports.** No CP-02 code imports `PersonalIntelligenceAgent`, `InsightAgent`, or any type from `personal_intelligence/shared/` — not `Goal`, not `IdentityFact`, not `Insight`, at any milestone, for any reason.
- **Shared Memory.** Every CP-01 fact CP-02 needs — identity and voice (read by Delivery and Stakeholder Communication for drafting), goals and reflection history (read by the Product Decision Specialist, though its Career Development mode remains v3-deferred and is not exercised by this plan) — is retrieved through the same `MemoryRetrievalPipeline`/`AgentMemory.retrieve()` surface every Memory Framework consumer uses.
- **Shared Executive.** Where CP-02 and CP-01 capabilities need to be coordinated in one request, that coordination happens through the Executive's own capability-based dispatch — never through one pack's code calling into another's.
- **Shared Context.** All scoping is via the existing `organization_id`/`user_id` fields on `SharedExecutionContext` — no second scoping mechanism, no cross-pack identifier, is introduced anywhere in this plan.

## 12. Tool Usage Strategy

Every CP-02 specialist is built holding a `ToolAdapter`, following the identical precedent `ResearchAgent` and every CP-01 specialist already established — this keeps the integration point consistent across the platform even though, as of this plan, **no v1/v2 CP-02 journey requires a tool that does not already exist.** No concrete tool category is exercised by any milestone in this plan. The Tool Framework integration point is wired, ready, and — for this implementation — entirely dormant, exactly as Architecture §16 (of the PRD) and Architecture §8.7 already anticipated: once an issue-tracker or project-management tool is registered on the platform, Delivery Specialist's future work would reach it through `ToolManager`, never directly.

## 13. Vision Usage Strategy

Vision Framework integration is named, in the PRD (§15) and Architecture (§14), as a future capability specifically for Discovery: captured research artifacts — photographed whiteboards, screenshots of user feedback — processed via `VisionRuntime`, the same forward-looking pattern CP-01's own Knowledge Intelligence already established.

**This is stated clearly as deferred, not planned, in this Implementation Plan.** No CP-02 specialist built under this plan constructs, holds, or references a Vision integration point. This is not a gap in the plan — it is a direct consequence of no concrete Vision provider existing anywhere on the platform, identical to the situation CP-01 itself shipped through.

## 14. Testing Strategy

Every milestone that produces a specialist (3 through 7) is held to the full testing standard the Development Guide §9 already establishes, applied per specialist:

| Test category | What it proves |
|---|---|
| **Unit tests** | Every domain model (§6) and memory-service method behaves correctly in isolation, built from hand-written fakes, never mocks. |
| **Integration tests** | The specialist's own `process()`/operation dispatch produces correct `SpecialistResponse`s across every operation it supports, including failure paths. |
| **Executive integration tests** | The specialist is capability-dispatchable, never declares `AgentCapability.MEMORY`, and — where applicable — never intercepts the Executive's own internal memory-retrieval tasks (Milestone 8 exercises this across all five specialists together). |
| **Regression tests** | The full platform test suite, including every prior CP-01 and CP-02 test, passes with zero failures after the new specialist is added. |
| **Architecture tests** | The platform's own AST-based dependency validator passes for every new module, with the dependency-boundary entry (§15) registered and correct. |

Milestones 1 and 2 are held to the same standard minus the Executive-integration category, which does not apply until a specialist exists to test it against. Every milestone's edge cases and failure scenarios are drawn directly from ARR §8's own Failure Mode Analysis — insufficient evidence, conflicting evidence, missing stakeholder context, and the rest — so that each specialist's test suite proves the behavior ARR already specified, rather than a different behavior invented during implementation.

**This section is itself the CP-02-specific test plan ARR §15 condition 3 required.** No further test-planning document is needed before Phase 4 begins.

## 15. Documentation Plan

The following documents are created or updated during implementation, one per relevant milestone:

- **A capability-level document** (Milestone 9), mirroring `Personal_Intelligence_Pack.md`.
- **Five agent-level documents** (Milestone 9), one per specialist, mirroring `Personal_Intelligence_Agent.md`/`Insight_Agent.md`.
- **An addendum to `Architecture.md`** (Milestone 9), folding in the ARR's own corrected memory-lifecycle citation and update/deletion convention — resolving ARR §15 condition 1.
- **`Roadmap.md`**, updated at every milestone's completion to reflect CP-02's real, current phase — not only at final release.
- **`Capability_Strategy.md`**, updated at Milestone 10 to reflect CP-02's release.
- **The platform's dependency-boundary registry** (`app/tests/architecture/dependency_rules.py`), updated at Milestone 3 — the earliest point at which CP-02 code exists for a boundary to classify. ARR §13 named this a "Phase 3 task" using the phasing understood at the time the ARR was written; under the Development Guide's now-formal, more granular lifecycle, a boundary entry cannot precede the code it classifies, so this plan schedules it correctly at the first milestone that produces code, not in this document itself.
- **Release notes and a completion summary** (Milestone 10), the two Development Guide §5 deliverables CP-01 did not produce a standalone version of, and CP-02 now will.

## 16. Risk Assessment

| Risk | Mitigation |
|---|---|
| **Architecture drift** — implementation quietly diverging from the approved Architecture during coding | Every milestone's Implementation Gate (§17) checks architecture compliance before the milestone closes; any genuine need to deviate returns to Phase 2 for review, per Development Guide §3's "No silent redesigns" — it is never resolved unilaterally inside a milestone. |
| **Memory duplication** — a specialist inventing its own ad hoc memory category instead of using one already approved | Milestones 1 and 2 establish the complete domain-model and memory-category catalogue *before* any specialist is built, so every later milestone has an existing category to use rather than a reason to invent one; §7 explicitly resolves the one place the PRD's own phrasing could have suggested a new category was needed. |
| **Executive coupling** — a specialist bypassing capability-based dispatch, or colliding with the Executive's own internal tasks | Milestone 8 exists specifically to prove, by test, that no specialist declares `AgentCapability.MEMORY` and that Dispatcher-based routing is the only path any specialist is reached through. |
| **Professional scope creep** — a specialist reaching into v3-scoped territory (full Portfolio Intelligence, Career Development) during v1/v2 implementation | §2 states the excluded scope explicitly; any specialist's implementation that appears to require v3 functionality is a signal to return to Phase 2 architecture review, not to build the v3 capability early and undocumented. |
| **Overengineering** — a specialist inventing a bespoke pattern instead of reusing the coordinator/state-machine/event/policy shape already proven by CP-01 | Every specialist in this plan is built to the identical structural shape CP-01's own specialists already established (Development Guide §3, "Simple over clever" and "Platform before features") — no milestone in this plan calls for a new architectural pattern. |

## 17. Implementation Gates

No milestone in §4 may close until all four of the following hold, mirroring the Development Guide §11 Code Review Checklist applied at milestone granularity:

- [ ] **Architecture respected** — the milestone's deliverables match what Architecture.md and this plan specify, with no undocumented deviation.
- [ ] **Tests passing** — the milestone's own tests, and the full platform regression suite, pass with zero failures.
- [ ] **Documentation updated** — any document this plan assigns to the milestone (§15) is current, not deferred to a later milestone.
- [ ] **No frozen interface modified** — verified by the platform's own architecture-enforcement suite, not by inspection alone.

## 18. Definition of Done (Phase 4)

Phase 4 (Implementation) is complete — and CP-02 is ready to enter Phase 5 (Verification) — when all ten milestones in §4 have individually passed their Implementation Gate (§17), with no milestone left partially complete or deferred without an explicit, documented reason. This is the CP-02-specific instantiation of the Development Guide's own platform-wide Definition of Done (§17 of that document); it does not relax or narrow it.

## 19. Release Readiness

Before CP-02 may enter Phase 8 (Release Candidate) as defined by the Development Guide, all of the following must hold simultaneously:

- All five specialists implemented, individually tested, and integration-tested against the Executive (Milestones 3–8).
- Every ARR §15 condition resolved: the Architecture.md addendum published (Milestone 9), Decision Record's structural evidence-enforcement proven by test (Milestone 1, exercised throughout), and this plan's own §14 serving as the required test plan.
- The dependency-boundary registration in place and passing the platform's architecture-enforcement suite (Milestone 3).
- Full platform regression suite green, with zero failures, including every CP-01 test.
- `Roadmap.md` and `Capability_Strategy.md` both current with CP-02's actual, shipped state.
- Release notes and a completion summary drafted (Milestone 10).

## 20. Phase 4 Handoff

When Phase 4 begins, developers receive: this Implementation Plan in full; the approved PRD, Architecture, and ARR it was built from; the ten-milestone sequence with each milestone's objectives, dependencies, deliverables, and acceptance criteria already defined (§4); the complete domain-model catalogue (§6) and memory-category catalogue (§7) needed to begin Milestone 1 without further design; the specialist rollout order and its justification (§8); the Executive- and Research-integration mechanisms already specified, requiring no new design (§9, §10); the CP-01 integration boundary, stated precisely enough to be checked by inspection at any point (§11); the full testing standard per specialist (§14); the risk register and its mitigations (§16); and the Implementation Gate every milestone is checked against (§17). Nothing beyond execution against this plan is required to begin Milestone 1.

---

## Implementation Readiness Assessment

**CP-02 is ready to enter Phase 4 (Production Implementation).**

The Architecture passed its Readiness Review with a verdict of READY WITH CONDITIONS, and all three of that Review's conditions are now concretely scheduled within this plan rather than left open: structural evidence-enforcement on Decision Records is a Milestone 1 deliverable; the Architecture.md documentation addendum is a Milestone 9 deliverable; and the required CP-02-specific test plan is §14 of this document itself. The one architectural open question this plan inherited — whether single-plan, multi-specialist Research delegation is available — has a fully sufficient, already-proven fallback (§10) that this plan builds against exclusively, so it blocks nothing.

Every milestone in §4 has a named dependency, a concrete deliverable, and an objective acceptance criterion. The specialist rollout order in §8 is justified by real dependency relationships, not convenience. The risk register in §16 names every category of risk this plan was asked to consider, each with a mitigation already built into the milestone sequence rather than deferred to be discovered during coding. No milestone in this plan requires touching a frozen interface, modifying CP-01, or introducing new platform mechanism.

Phase 4 may begin at Milestone 1.
