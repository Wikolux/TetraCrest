# Tetra OS — Version 1 Platform Baseline

| | |
|---|---|
| **Scope** | The platform as a whole, after two full Capability Pack releases (CP-01, CP-02) — not a single capability |
| **Authority** | An operational baseline document, not a fifth governance authority. It reports status against, and never outranks, the repository's four highest-authority documents ([MASTER_BLUEPRINT.md](../MASTER_BLUEPRINT.md), [PRODUCT_PHILOSOPHY_FREEZE_v1.md](../PRODUCT_PHILOSOPHY_FREEZE_v1.md), [ARCHITECTURE_FREEZE_v1.md](../ARCHITECTURE_FREEZE_v1.md), [VERSION_1.0_MILESTONE_ZERO.md](../VERSION_1.0_MILESTONE_ZERO.md)) — the same relationship [CAPABILITY_READINESS.md](../CAPABILITY_READINESS.md) already has to those four, one layer up in scope. |
| **Relationship to `VERSION_1.0_MILESTONE_ZERO.md`** | That document is the permanent, one-time historical record of the moment Version 1.0's *platform engineering* was declared complete — written when CP-02 existed only through governance review, before a line of its code shipped. This baseline is the next chapter, not a replacement: it consolidates what has actually shipped since (CP-01 through the Insight Engine, and CP-02 through full release) into a single, current reference point. `VERSION_1.0_MILESTONE_ZERO.md` itself is not revised to reflect this — by its own stated nature, it is written once. |
| **Status** | Established. Updated only when a new Capability Pack releases, a new Application ships, or a genuine platform-level change occurs — never rewritten to relitigate history. |
| **Last established** | 2026-08-03, following CP-02's full release and freeze (Milestone 10) and the Version 1 Program Review that preceded this document. |

This document exists to answer one question in one place: **what, exactly, can every future Capability Pack and Application assume is already true, stable, and built?** Everything below is verified against the actual codebase and test suite at the time this document was established, not against plans for either.

---

## Platform Identity

**Purpose**: Tetra OS (the AI Operating System, `app/services/ai/`) exists so that adding a new AI-driven capability is a registration, not a rewrite — the platform's own answer to what happens when a product has more than one AI capability and each one is tempted to become a bespoke, vendor-coupled integration (see [Vision.md](Vision.md)).

**Vision**: an agentic operating system — one Executive that plans and delegates, a growing roster of Specialist agents, a Tool Framework giving agents real-world reach, and a Memory/Retrieval layer giving every agent continuity across sessions rather than starting from zero each time. The same architecture serves an individual and an organization without becoming a different architecture (Vision.md's "Personal AI Vision" and "Enterprise Vision").

**Design philosophy**: compose, never duplicate; provider-agnostic by construction; never raise, always return a structured result; Open/Closed at every extension point; identity is structural, not incidental; architecture before implementation; no speculative abstraction. (Vision.md, "Design Philosophy" — restated here only as a pointer, not reproduced in full.)

**Architectural principles**: every capability is reachable the same way, through a Framework's Runtime/Executor; every execution is observable (structured events, metrics, identity); every failure mode is a first-class return value; every registry is the single extension point for its domain; tests are the specification (Vision.md, "Guiding Principles").

## Platform Components

Summarized only — see each component's own architecture documentation for detail; nothing below is rewritten from those sources.

| Component | What it does | Status at this baseline |
|---|---|---|
| **Executive Framework** | Plans, decides, and delegates by capability, never by hardcoded name | Frozen since M20.7; proven across 8 specialists in production use (§"Executive Architecture," below) |
| **Runtime** | The working, provider-agnostic conversational execution engine | Frozen since M20.7; every specialist across both released packs generates exclusively through it |
| **Memory** | The durable understanding substrate — identity, goal, reflection, insight, and professional memory | Frozen since M20.7; full four-method contract (`remember`/`retrieve`/`forget`/`search`) complete since CP-01.2 |
| **Prompt Builder** | Assembles retrieved context and a request into what the Runtime sends for generation | Frozen since M20.7; never bypassed by any specialist in either released pack |
| **Specialist Framework** | The extension point every domain-expert reasoning unit is built through | Frozen since M20.7; the platform's single most-exercised extension point — 8 specialists built against it |
| **Tool Framework** | Gives specialists real-world reach | Frozen since M20.7 as a contract; zero concrete tools registered platform-wide, by design |
| **Vision Framework** | Gives the platform the ability to understand what it is shown | Frozen since M20.7 as a contract; zero concrete providers registered platform-wide, by design |
| **Conversation Framework** | The provider-agnostic language interface every generative capability is built through | Frozen since M20.7; zero concrete vendor providers registered, by design |
| **Event System** | Structured, typed event trails for every execution engine on the platform | Frozen since M20.7; every specialist across both packs emits its own typed event vocabulary through it, never a bespoke mechanism |
| **Registry System** | The generic, provider-agnostic registration mechanism every framework's extension point is built from | Frozen since M20.7; consolidated (ADR-0002) from five previously-independent implementations |
| **Middleware** | Shared cross-cutting execution behavior (retry, timeout, cancellation) | Frozen since M20.7; composed by every executor, never reimplemented per-capability |
| **Kernel** | The platform's execution physics — identity, retry, timeout, cancellation, event, and state contracts | Stable *as a contract*; its own execution engine (`KernelRuntime.execute()`) is intentionally not yet implemented — a named, permanent design state (§"Known Version 1 Limitations," below) |
| **Architecture Enforcement** | AST-based dependency validation, run as part of the platform's own test suite | Frozen since M20.7; re-verified clean this baseline (zero boundary/vendor violations across both packs) |

## Released Capability Packs

| Capability | Status | Release Level | Dependencies | Maturity |
|---|---|---|---|---|
| **CP-01 — Personal Intelligence** (incl. CP-01.3 Insight Engine) | Released | CRL-5 | None (the foundation every later pack reads from) | Two specialists (`PersonalIntelligenceAgent`, `InsightAgent`), 6 memory categories, 317 tests, zero regressions since release |
| **CP-02 — Product Management Intelligence** | Released, frozen | CRL-5 | CP-01 (read-only, via shared memory, never direct import) | Five specialists, 10 memory categories, 51 operations, 766 tests, zero regressions across all ten milestones |

See [Personal_Intelligence_Pack.md](../04_CAPABILITIES/Personal_Intelligence_Pack.md) and [Product_Management_Intelligence.md](../04_CAPABILITIES/Product_Management_Intelligence.md) for each pack's own full capability guide, and [CP-02_RELEASE_CANDIDATE.md](../08_CAPABILITY_PACKS/CP-02_Product_Management_Intelligence_Pack/CP-02_RELEASE_CANDIDATE.md) for CP-02's complete closure record.

**Not a released pack, but foundational**: `ResearchAgent` (M18) is the platform's first concrete specialist and the reference implementation every later specialist — including every one in both released packs — pattern-matches against. It predates the CP-numbering convention (introduced at M20.7) and is not itself a numbered Capability Pack, but it is real, shipped, production code, not a template.

## Memory Taxonomy

Every durable fact any specialist remembers is an ordinary `Memory` row, tagged with a pack-namespaced `memory_type` string — never a new table, schema, or storage mechanism (ADR-0006; Architecture Freeze §"Memory"). Two namespaces exist today:

| Namespace | Owner | Categories | Purpose |
|---|---|---|---|
| `personal_*` | CP-01 | `personal_identity`, `personal_goal`, `personal_project`, `personal_reflection`, `personal_preference` (the five in `ALL_MEMORY_TYPES`), plus `personal_insight` (CP-01.3, deliberately excluded from that tuple so the Insight Engine's own bulk-analysis corpus never re-analyzes its prior output — 6 categories total) | A durable, evolving model of who the user is, what they're working on, and what they've decided before |
| `product_*` | CP-02 | `product_context`, `product_feature`, `product_roadmap`, `product_metric`, `product_discovery_finding`, `product_research_finding`, `product_decision`, `product_stakeholder`, `product_pm_craft_record`, `product_delivery_artifact` (10 categories) | Professional product-management practice, built on top of CP-01's identity/goal model without duplicating it |

**Namespace rules** (ADR-0006, formalized permanently): a pack does not introduce a new `memory_type` for a business concept merely because that concept has its own name in its domain model. A new type is warranted only when the concept needs to be retrieved, owned, retained, or reasoned about differently from a category the pack (or a pack it builds on) already has approved. Zero categories have ever been added to either namespace beyond what each pack's own Architecture originally approved, and the two namespaces have zero overlap — verified fresh at this baseline (16 total categories platform-wide, all namespaced, all distinct).

**Ownership discipline**: every category has exactly one owning specialist for writes (CP-02's Delivery Artifact category is the one documented exception — owned by Delivery, with Stakeholder Communication reusing it for a purely additive `COMMUNICATION_DRAFT` artifact type, per that pack's own Architecture §6). Every write is append-only; every deletion is user-requested via `AgentMemory.forget()`, never an automatic or silent removal.

## Executive Architecture

**Delegation and routing**: the Executive plans a task graph and delegates by declared `AgentCapability`, never by a specialist's name — `Dispatcher` matches purely on capability. No specialist has ever been hardcoded into the Executive's own dispatch logic, across 8 specialists and two packs.

**Capability matching**: every specialist declares only the capabilities it genuinely has. `AgentCapability.MEMORY` is deliberately never declared by any Capability Pack specialist — declaring it would make a specialist a candidate for the Executive's own internal memory-retrieval tasks, which expect a raw `ContextPackage` back, not a `SpecialistResponse`. This collision-avoidance rule has held, without exception, across every specialist built to date.

**Execution lifecycle**: a specialist must be constructed and initialized to `READY` state before the Executive's real delegation path (`AgentExecutor.execute()`) will run it — a genuine platform lifecycle requirement, discovered in practice during CP-02's own Executive-integration work, not yet folded back into `Adding_Agent.md` (tracked as deferred technical debt, not hidden).

**No implementation detail beyond this** — see [Executive_Agent.md](../05_AGENTS/Executive_Agent.md) and [Specialist_Framework.md](../03_INTELLIGENCE/Specialist_Framework.md) for the full architecture.

## Runtime Architecture

**Runtime**: every specialist generates exclusively through `AIRuntime`, reached only via `RuntimeAdapter` — never constructed directly by a specialist. Verified structurally (not by convention) across both released packs.

**Prompt Builder**: every generation is preceded by a real `PromptBuilder`-produced `PromptPackage`; no specialist has ever been found hand-assembling a prompt.

**Adapters**: `MemoryAdapter`, `ToolAdapter`, and `RuntimeAdapter` are the only seams a specialist is permitted to depend on for memory, tools, and generation respectively — never the underlying subsystems (`MemoryRetrievalPipeline`, `ToolExecutor`, `AIRuntime`) directly. This is what makes every specialist trivially fakeable in tests without touching a real provider.

**Execution model**: request → automatic evidence retrieval → structured reasoning (framework-applied where relevant) → either a synthesized, evidence-cited response or an honest evidence-gap admission — never a fabricated conclusion, and never an exception escaping uncaught. Every execution engine on the platform returns a structured result; none propagates a bare exception to its caller.

## Governance

**Document hierarchy**: four highest-authority documents (`MASTER_BLUEPRINT.md`, `PRODUCT_PHILOSOPHY_FREEZE_v1.md`, `ARCHITECTURE_FREEZE_v1.md`, `VERSION_1.0_MILESTONE_ZERO.md`), each written once and not revised as the platform grows; operational trackers (`Roadmap.md`, `Capability_Strategy.md`, `CAPABILITY_READINESS.md`, this document) that report against those four but never outrank them.

**Freezes**: the Architecture Freeze (M20.7) is the only architecture-level freeze on the platform, and it has now held, unmodified, through two full Capability Pack builds — the strongest evidence available that it was the right freeze to declare.

**ADRs**: one exists (ADR-0006, memory-type discipline), accepted and applied consistently across every CP-02 memory-category decision since.

**Roadmap**: `Roadmap.md` is the living, chronological, milestone-by-milestone record — kept current at every milestone close across both released packs, re-verified accurate at this baseline.

**Capability lifecycle**: the nine-phase Development Guide lifecycle (PRD → Architecture → ARR → Implementation Plan → Implementation → Verification → Documentation → Integration Validation → Release), proven once in full by CP-02, phase by phase, gate by gate.

**Release process**: a released Capability Pack updates `Roadmap.md` and `Capability_Strategy.md` at release, and `CAPABILITY_READINESS.md`'s CRL — the one process gap this baseline's own predecessor review found (`CAPABILITY_READINESS.md` lagged CP-02's actual status for several milestones) has been corrected and should be treated as a standing Implementation Gate item going forward, not merely a one-time fix.

## Platform Health

| Dimension | Assessment |
|---|---|
| **Architectural stability** | High. Zero frozen interfaces modified across two full pack builds; zero new platform primitives required by either pack. |
| **Governance maturity** | High. Document-authority hierarchy has been tested directly (twice, across the two reviews preceding this document) and held — a reviewer correctly declined to edit a permanent historical document both times. |
| **Implementation maturity** | High for what's shipped (two packs, 8 specialists, zero regressions); unproven beyond two data points for packs not yet attempted (Vision-registered providers, Tool-registered providers, a third Capability Pack). |
| **Documentation maturity** | High. 67 documents (up from the 52 recorded at Version 1.0's own Milestone Zero), zero broken links verified at this baseline, one stale cross-reference found and corrected during CP-02's own closeout. |
| **Testing maturity** | High. 3,134 tests platform-wide, hand-written fakes only, zero mocks, zero regressions across both packs' full histories. |

## Known Version 1 Limitations

Documented only where real and accepted — nothing here is invented:

- **`ExecutivePlanner` is deterministic and template-based**, across the Executive and every specialist planner on the platform. No adaptive or self-tuning planning exists anywhere. A deliberate choice, not an unfinished feature (Vision.md, "No speculative abstraction").
- **No live deployment yet exercises rich, operation-specific Executive delegation.** The Dispatcher/`AgentExecutor` plumbing is proven end to end; constructing a specialist's rich request payload from a live conversation is not yet built — true for both released packs, a platform-level gap, not a pack-level one.
- **Tool and Vision Frameworks are provider-agnostic by construction, with zero concrete providers registered.** This is the intended design state (capability-first, vendor-last), not an oversight — but it means no Capability Pack can yet exercise a real tool call or a real vision-assisted capture end to end.
- **`KernelRuntime.execute()` remains intentionally unimplemented.** The Kernel is a contract-first foundation; the Runtime is the platform's actual working execution engine. A long-standing, deliberately retained dual-track design, not a defect.
- **No durable event persistence.** Every `EventPublisher` on the platform is in-process and synchronous; events are lost the moment the holding process exits. Real auditability, compliance logging, or an executive dashboard would need this built first (Future_Enterprise_Architecture.md).
- **No multi-process/horizontal-scaling design exists yet** for the AI Operating System specifically — registries and event publishers are in-process today. Not addressed, not hidden.
- **No multi-tenant or team-wide personal intelligence.** CP-01 remains scoped to one individual by design; organization-wide intelligence is deliberately deferred to a future Enterprise-layer Application (§"Application Layer Definition," below).

---

## Platform Freeze

**Version 1 Platform Architecture is frozen** — this is a ratification of the freeze [ARCHITECTURE_FREEZE_v1.md](../ARCHITECTURE_FREEZE_v1.md) already declared at M20.7, not a new declaration issued by this document. What this baseline adds is evidence: the freeze has now held, unmodified, through two complete Capability Pack builds, ten CP-02 milestones, and 3,134 tests, with zero exceptions.

Future work proceeds by:
- **New Capability Packs**, built entirely on the existing extension points, exactly as CP-01 and CP-02 were.
- **Applications**, combining multiple Capability Packs into real-world workflows (§"Application Layer Definition," below) — never by modifying a Capability Pack's own frozen boundary.
- **Version 2**, only if and when sustained Capability Pack development discovers a genuine limitation Version 1's foundation cannot resolve by extension alone (`VERSION_1.0_MILESTONE_ZERO.md` §14) — not scheduled, not assumed, not a default outcome.
- **Maintenance and bug fixes**, against any released pack's own stated guarantees.

The platform architecture itself does not change unless a future governance decision — reviewed with at least the rigor CP-02's own Architecture Readiness Review demonstrated — explicitly reopens it.

## Version 1 Release Summary

Verified numbers only, re-run at this baseline:

| Metric | Value |
|---|---|
| Released Capability Packs | 2 (CP-01, CP-02) |
| Total specialists, platform-wide | 8 (`ResearchAgent`; CP-01's `PersonalIntelligenceAgent`, `InsightAgent`; CP-02's five) |
| Total memory categories | 16 (6 `personal_*`, 10 `product_*`) |
| Total platform tests | 3,134 passing, 0 failing |
| — of which, CP-01 (`app/tests/personal_intelligence/`) | 317 |
| — of which, CP-02 (`app/tests/product_management/`) | 766 |
| Architecture-enforcement suite (`app/tests/architecture/`) | 13 passing |
| `ruff check app/` | Clean |
| Architecture status | Frozen since M20.7; zero modifications across both packs |
| Governance status | Current; one stale cross-reference found and corrected (CP-02 closeout); zero other inconsistencies found across three successive audits |

## Application Layer Definition

The platform's architecture has a fourth layer, implicit in existing documents but not previously named as its own tier. This document formalizes it:

```
Platform (Tetra OS — frozen)
    ↓
Capability Packs (CP-01, CP-02, ... — reusable domain intelligence)
    ↓
Applications (Forge, Learning OS, Career OS, ... — real-world workflows)
    ↓
Connectors (integrations to external services — calendars, CRMs, issue trackers, ...)
```

- **Capability Packs provide reusable intelligence.** A pack is domain expertise — Discovery, Product Decision, Delivery, and so on — built once, read by anything above it, never coupled to a specific end-user workflow.
- **Applications combine multiple Capability Packs to solve real-world workflows.** An Application is not itself a new specialist or a new memory category — it is a coordinated experience built from packs that already exist, exactly the way `Capability_Strategy.md`'s already-named **Personal Operating System Pack** ("a later, coordinated bundle of several domain packs... scoped for an individual user") and **Enterprise Operating System Pack** ("a coordinated bundle scoped for organizational workflows") already describe, without previously naming the layer they sit on. This document gives that already-real concept its proper name.
- **Connectors integrate external services.** A Connector is how an Application (or, more rarely, a pack's own Tool) reaches a real calendar, CRM, or issue tracker — the concrete Provider/Tool implementations the platform has, by design, not yet registered (§"Known Version 1 Limitations," above).
- **Applications never import a Capability Pack's specialist code directly.** The same Pack Independence rule `Capability_Strategy.md` already enforces between packs applies one layer up: an Application reaches a pack's capability only through the Executive's existing capability-based dispatch and the shared Memory Framework — never by importing `DiscoverySpecialist`, `PersonalIntelligenceAgent`, or any other pack-internal type by name. An Application that finds itself needing to has found a pack's own missing operation (Category B, that pack's own lifecycle), not a reason to reach around the boundary.

No application is designed here — only the relationship between the four layers.

## Future Application Registry

Candidate Applications, named without implementation priority, milestone, or roadmap commitment — exactly as `BACKLOG.md` treats a vision-stage idea. Each is cross-referenced against what already exists in governance, so this registry reconciles with prior documents rather than inventing a parallel set of concepts.

| Application | Purpose | Capability Packs Expected to Support It | Existing Precedent |
|---|---|---|---|
| **Forge** | A builder/creation workspace — an Application for making things (products, content, plans) rather than managing an existing practice | CP-02 (Product Management), a future Coding/Software Engineering pack (CP-05, reserved) | No prior name in governance; introduced here for the first time |
| **Learning OS** | A continuous learning companion — study planning, skill tracking, curriculum pacing | CP-01 (goals/reflection), a future Education pack (vision-stage, `CAPABILITY_READINESS.md`) | Vision.md's own "Learning agent for study assistance"; CP-01 PRD's deferred Learning Intelligence (v2) |
| **Career OS** | Career growth across roles and disciplines — coaching, decision support, craft development | CP-01 (Career Coaching, PRD §10.6), CP-02 (PM Craft Record / Career Development byproduct), a future Education pack | This reconciles a real naming confusion from this conversation's own prior turns: "Career Intelligence" was proposed twice as a next *Capability Pack* and was not a real reservation. As an **Application** — a workflow built from packs that already exist — "Career OS" requires no new pack, no new CP-number, and no conflict with `Capability_Strategy.md`'s existing CP-03–CP-08 reservations. |
| **NGO OS** | Coordinated workflows for nonprofit operations — grant management, program reporting, donor communication | A future Enterprise/Business-adjacent pack, Stakeholder Communication patterns (CP-02) | No prior name in governance; introduced here for the first time |
| **Real Estate OS** | Coordinated development/investment/construction/facilities/compliance workflows | A future Real Estate Intelligence pack (vision-stage, `CAPABILITY_READINESS.md`), Enterprise Operating System Pack | Directly named already: `Future_Enterprise_Architecture.md`'s own "Organization Operating Systems" section cites the project's `.ai/ROADMAP.md` Phase 6, "Real Estate Operating System," verbatim |
| **Business OS** | Coordinated organizational workflows — CRM, sales, procurement, reporting | CP-02 (roadmap/decision patterns), a future Finance pack (CP-03, reserved), the already-named Enterprise Operating System Pack | Directly named already: `Capability_Strategy.md`'s "Enterprise Operating System Pack" and `Future_Enterprise_Architecture.md`'s "Organization Operating Systems" (`.ai/ROADMAP.md` Phase 5, "Business Operating System") |

No implementation plan, milestone, or priority is assigned to any row above.

## Platform Engineering Lessons (Consolidated, Version 1)

Distilled from CP-01, CP-01.3, and CP-02's combined history — see `Roadmap.md` and `CP-02_RELEASE_CANDIDATE.md` §14 for the full pack-level retrospectives this consolidates.

- **Architecture**: an architecture that reuses one proven extension shape scales across 8 specialists and two structurally different packs without needing a variant. The cost is real — CP-02 could not shortcut around a genuine platform lifecycle requirement it discovered — but the payoff is that nothing platform-level has needed to change across either pack's full build.
- **Governance**: a permanence-graded document hierarchy only works if every reviewer checks a document's own stated nature before editing it. This held under direct test, twice, in this program's own recent history.
- **Testing**: hand-written fakes against real, enforced contracts, never mocks, remains unbroken at 3,134 tests. The one process failure that did occur (CP-02's `RaciRole` finding) was a verification-methodology gap — searching one reference pattern instead of three — not a testing-discipline gap.
- **Documentation**: documentation written before code, independently reviewed, catches real defects cheaply — proven twice, not once (CP-02's own ARR, and this baseline's own predecessor review catching a stale `BACKLOG.md` cross-reference).
- **Implementation**: a Capability Pack can be built to full release with zero platform code changes when it is disciplined about reuse. This is no longer a claim; it is CP-02's own record.

---

**Tetra OS Version 1 Platform Baseline Established.**

**Version 1 is now the official foundation for all future Capability Packs and Applications.**
