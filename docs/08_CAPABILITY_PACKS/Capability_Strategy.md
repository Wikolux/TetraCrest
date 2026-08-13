# Capability Pack Strategy

As of [ARCHITECTURE_FREEZE_v1.md](../ARCHITECTURE_FREEZE_v1.md), the AI Operating System's architecture is frozen at version 1.0. This document describes what comes next: not "M21, M22, ..." as further architecture milestones, but **Capability Packs** — modular, domain-specific bundles of specialists, tools, and providers built entirely on top of the frozen platform.

## What a Capability Pack Is

A Capability Pack is a bundle of one or more concrete `SpecialistAgent`s, `BaseTool`s, and (optionally) capability providers (`ConversationProvider`/`BaseVisionProvider` implementations), plus whatever prompts, policies, and events are specific to its domain — registered into the existing registries, using the existing extension points, with **zero modification to any frozen interface**.

`ResearchAgent` (M18) is, in retrospect, the template every future pack follows: it is a `SpecialistAgent`, it uses `ToolAdapter`/`MemoryAdapter`/`RuntimeAdapter` rather than reaching into the underlying frameworks directly, and it registers itself into `SpecialistRegistry` and `AgentRegistry` without touching either. A Capability Pack is what you get when you deliberately package "one or more `ResearchAgent`-shaped things, for a specific domain" as a coherent, named unit. `PersonalIntelligenceAgent` (CP-01, Phase 3) is the first pack actually built this way — see [Personal_Intelligence_Pack.md](../04_CAPABILITIES/Personal_Intelligence_Pack.md).

## The Reuse Contract

Every Capability Pack **must** reuse, and **must not** change:

- **Runtime** (`AIRuntime`) — for any conversational/LLM capability the pack needs.
- **Tools** (`ToolManager`/`ToolExecutor`/`BaseTool`) — for any action the pack's specialists need to take.
- **Memory** (`AgentMemory`/`MemoryAdapter`/`MemoryRetrievalPipeline`) — for any retrieval/context the pack's specialists need.
- **Prompt Builder** (`PromptBuilder`) — for assembling any prompt the pack sends to the Runtime.
- **Vision** (`VisionRuntime`, once a concrete provider exists) — for any visual understanding the pack needs.
- **Shared Execution Context** (`SharedExecutionContext`) — for identity, propagated via `.child()`/`parent_shared` exactly as every existing framework already does.

A pack that finds itself needing to modify one of these to do its job has found a real platform gap, not a pack-level concern — that's a conversation about a platform MAJOR version (see the Compatibility Policy in [ARCHITECTURE_FREEZE_v1.md](../ARCHITECTURE_FREEZE_v1.md)), not something to route around inside the pack.

Memory reuse specifically carries one further, binding rule, discovered during CP-02 and formalized in [ADR-0006](../ADR/ADR-0006.md): a pack does not introduce a new `memory_type` for a business concept merely because that concept has its own name in its Product Artifact Model. A new type is warranted only when the concept needs to be retrieved, owned, retained, or reasoned about differently from a category the pack (or a pack it builds on) already has approved.

## Anatomy of a Capability Pack

Mirroring [Adding_Agent.md](../06_DEVELOPMENT/Adding_Agent.md) and [Adding_Tool.md](../06_DEVELOPMENT/Adding_Tool.md), a typical pack consists of:

1. **One or more `SpecialistAgent` implementations**, each registered in `SpecialistRegistry` with an accurate `specialization`/`supported_tasks`, and in `AgentRegistry` for generic discovery.
2. **Zero or more `BaseTool` implementations** specific to the pack's domain (e.g., a Finance pack might register a `MarketDataTool`; a Coding pack might register a `CodeExecutionTool`), each registered in `ToolRegistry` with accurate `category`/`capabilities`/`permissions`.
3. **Zero or more concrete providers** (a domain-specific `ConversationProvider` or `BaseVisionProvider` implementation), if the pack needs a vendor integration no other pack already registered — registered in the relevant registry.
4. **Pack-specific value objects and events**, following the existing per-specialist pattern (e.g., `ResearchReport`/`ResearchEvent` for Research) — never reusing another pack's concrete types, and never requiring a change to the generic `SpecialistAgent`/`AgentMemory`/`BaseTool` contracts to express them.
5. **A pack-specific policy**, layered on top of (never duplicating) `SpecialistExecutionPolicy`/`RetryPolicy` — following `ResearchPolicy`'s exact precedent.

## Pack Independence

Packs must not import each other's concrete types. A Finance pack's specialist must never import a Trading pack's specialist by name — if one pack's specialist needs another's capability, that need is expressed through the Executive's existing capability-based dispatch (`Dispatcher`/`SpecialistDispatcher`), exactly the same way `ExecutiveAgent` already dispatches to `ResearchAgent` without knowing it exists by name. This is the same "never import a concrete specialist" rule already enforced by `app/tests/architecture/` for the Specialist Framework itself — packs extend that boundary, they don't get an exception from it.

This rule holds even for a pack explicitly designed to build *on top of* another one. CP-02 (Product Management Intelligence, [PRD.md](CP-02_Product_Management_Intelligence_Pack/PRD.md)) is the first pack specified this way — it reuses CP-01's identity/goal/reflection model, but only by reading the same underlying Memory Framework facts CP-01 already writes and, where delegation is needed, through Executive capability-based dispatch — never by importing `PersonalIntelligenceAgent` or any other CP-01 type directly. "Built on top of" describes what a pack's product depends on conceptually, not a license for direct code coupling.

## Example Capability Packs

The following is the platform's own current thinking on what packs come next, not a commitment or a schedule. Each is described in terms of what it would register, following the anatomy above.

| Pack | What it would register |
|---|---|
| **Finance Pack** | Specialists for financial analysis/planning; tools for market data, spreadsheet/ledger access; possibly a domain-specific provider for a financial-data vendor |
| **Trading Pack** | Specialists for trade analysis and execution planning; tools for market data feeds and (with real caution around execution safety) order placement |
| **Coding Pack** | Specialists for code review/generation/debugging; tools for code execution, repository access, test running |
| **Vision Pack** | The first concrete Vision Framework providers (image/document/extraction/analysis) — the pack that finally exercises `VisionRuntime` end to end |
| **Marketing Pack** | Specialists for campaign planning/copywriting; tools for analytics/ad-platform integrations |
| **Legal Pack** | Specialists for contract review/legal research; tools for document retrieval and citation lookup |
| **Healthcare Pack (Health Intelligence Pack, CP-08)** | A lifelong AI health companion — Health Profile, Wellness, Nutrition, Emergency Response, Doctor Collaboration, and Health Companion specialists — always in a clearly supportive, non-diagnostic role (Master Blueprint §15). Vision registered in [BACKLOG.md](../BACKLOG.md)'s Health Intelligence Cluster; not yet PRD'd, not scheduled |
| **Research Pack** | Already exists (M18, `ResearchAgent`) — the reference implementation every other pack in this list follows |
| **Creative Pack** | Specialists for writing/design ideation; tools for asset generation/retrieval |
| **Sales Pack** | Specialists for lead qualification/outreach drafting; tools for CRM data access |
| **CRM Pack** | Specialists for customer-relationship workflows; tools for CRM system integration |
| **HR Pack** | Specialists for hiring/onboarding workflows; tools for HR-system integration |
| **Education Pack** | Specialists for tutoring/curriculum planning; tools for content retrieval |
| **Executive Assistant Pack** | Specialists for scheduling/correspondence drafting; tools for calendar/email integration |
| **Personal Intelligence Pack (CP-01)** | **Implemented (v1 + Insight Engine).** The identity/memory/goal/reflection foundation, plus deterministic pattern/habit/contradiction/alignment detection and proactive recommendations — not a bundle of other packs, but the durable, evolving model of the user every other pack reads from. See its [PRD](CP-01_Personal_Intelligence_Pack/PRD.md), [Architecture](CP-01_Personal_Intelligence_Pack/Architecture.md), [Implementation](CP-01_Personal_Intelligence_Pack/Implementation.md), and [Implementation_Insight_Engine](CP-01_Personal_Intelligence_Pack/Implementation_Insight_Engine.md). |
| **Product Management Intelligence Pack (CP-02)** | **Implemented, Version 1 complete and frozen.** All ten implementation milestones complete; all five specialists — Discovery, Product Decision, Delivery, Strategy & Portfolio, Stakeholder Communication — implemented, integration-validated against the Executive, and fully documented. The first pack built explicitly on top of another pack (CP-01), reading its identity/goal/reflection model through the existing Memory Framework and Executive dispatch rather than duplicating or importing it. No further architectural work against this version — only maintenance and bug fixes; future enhancements occur through a Version 2 or a future Capability Pack built on top of CP-02. See its [PRD](CP-02_Product_Management_Intelligence_Pack/PRD.md), [Architecture](CP-02_Product_Management_Intelligence_Pack/Architecture.md), [ARR](CP-02_Product_Management_Intelligence_Pack/ARR.md), [Implementation Plan](CP-02_Product_Management_Intelligence_Pack/Implementation_Plan.md), [Capability Guide](../04_CAPABILITIES/Product_Management_Intelligence.md), [Production Readiness Report](CP-02_Product_Management_Intelligence_Pack/Production_Readiness_Report.md), and [Release Candidate record](CP-02_Product_Management_Intelligence_Pack/CP-02_RELEASE_CANDIDATE.md). |
| **Personal Operating System Pack** | Distinct from the Personal Intelligence Pack above: a *later*, coordinated bundle of several domain packs (Finance, Executive Assistant, Learning) scoped for an individual user, built on top of the Personal Intelligence Pack's foundation — see [Vision.md](../00_OVERVIEW/Vision.md)'s "Personal AI Vision" |
| **Enterprise Operating System Pack** | A coordinated bundle scoped for organizational workflows (CRM, Sales, HR, Finance together) — see [Future_Enterprise_Architecture.md](../07_ENTERPRISE/Future_Enterprise_Architecture.md)'s "Organization Operating Systems" |

## Numbering Convention

Going forward, work is tracked as **CP-NN** rather than **MNN**. **CP-01 was confirmed as the Personal Intelligence Pack** — promoted to first in the sequence (superseding this document's original placeholder ordering, not silently renumbered) specifically because it is the identity/memory/goal foundation every other pack is designed to read from (see §"What CP-01 Establishes for Every Later Pack," below). Phase 1 ([PRD.md](CP-01_Personal_Intelligence_Pack/PRD.md)), Phase 2 ([Architecture.md](CP-01_Personal_Intelligence_Pack/Architecture.md)), and Phase 3 v1 ([Implementation.md](CP-01_Personal_Intelligence_Pack/Implementation.md)) are all complete — CP-01 is now the reference Capability Pack this whole document's "Anatomy of a Capability Pack" is written from, and every pack below should pattern-match against `PersonalIntelligenceAgent` the same way earlier docs pointed at `ResearchAgent`.

- **CP-01**: Personal Intelligence Pack — **Phase 1 + Phase 2 + Phase 3 v1 + Phase 4 (Insight Engine) complete** (Identity, Goal, Project, Reflection, Preference, plus pattern/habit/contradiction/alignment detection, periodic reflections, proactive recommendations, and an evolving profile; Decision/Learning/Communication/Business/Productivity/Relationship/Knowledge/Life Intelligence deferred to a later phase)
- **CP-02**: Product Management Intelligence Pack — **all ten implementation milestones complete; Version 1 released and frozen (Milestone 10, Release Candidate & Capability Freeze).** See [PRD.md](CP-02_Product_Management_Intelligence_Pack/PRD.md), [Architecture.md](CP-02_Product_Management_Intelligence_Pack/Architecture.md), [ARR.md](CP-02_Product_Management_Intelligence_Pack/ARR.md), [Implementation_Plan.md](CP-02_Product_Management_Intelligence_Pack/Implementation_Plan.md), [Production_Readiness_Report.md](CP-02_Product_Management_Intelligence_Pack/Production_Readiness_Report.md), and [CP-02_RELEASE_CANDIDATE.md](CP-02_Product_Management_Intelligence_Pack/CP-02_RELEASE_CANDIDATE.md) (the final assembled record: statistics, the full Capability Traceability Matrix, and the freeze declaration). All three of the ARR's READY WITH CONDITIONS items are resolved (Milestone 9); both findings the Milestone 9 Production Readiness Report left open are closed (Milestone 10 — one genuine gap fixed, one false finding corrected). All five specialists (Discovery, Product Decision, Delivery, Strategy & Portfolio, Stakeholder Communication) are implemented, integration-validated against the Executive, and fully documented (capability guide: [Product_Management_Intelligence.md](../04_CAPABILITIES/Product_Management_Intelligence.md); developer guide: [Adding_Product_Management_Specialists.md](../06_DEVELOPMENT/Adding_Product_Management_Specialists.md); five per-specialist agent guides under `docs/05_AGENTS/`) — see [Roadmap.md](../00_OVERVIEW/Roadmap.md) for the full milestone-by-milestone history. The first pack specified to build on top of another Capability Pack (CP-01) rather than the platform alone — specializing Personal Intelligence into professional product-management practice (discovery, strategy, delivery, stakeholder communication, portfolio, career development) without duplicating or modifying it. **Frozen**: no further architectural work against this version; only maintenance and bug fixes; future enhancements occur through Version 2 or a future Capability Pack built on top of CP-02, exactly as CP-02 was built on top of CP-01. A "Career Intelligence" pack has been named as the next major initiative outside this document; note that **CP-03 through CP-08 are already reserved** (Finance & Accounting, Trading & Investment, Software Engineering, Marketing & Growth, Enterprise Operating System, Health Intelligence — see §"Numbering Convention," below) and no "Career Intelligence" pack appears in this registry, `BACKLOG.md`, or the Master Blueprint under that name. A genuinely new pack requires its own Phase 1 PRD and a numbering decision recorded here first (the next open identifier is **CP-09**) — this document is not silently renumbered to accommodate it.
- **CP-03**: Finance & Accounting Capability Pack
- **CP-04**: Trading & Investment Capability Pack
- **CP-05**: Software Engineering Capability Pack
- **CP-06**: Marketing & Growth Capability Pack
- **CP-07**: Enterprise Operating System Capability Pack
- **CP-08**: Health Intelligence Pack — reserved identifier only, **CRL-0, not scheduled**. Vision (Health Profile, Wellness, Nutrition, Emergency Response, Doctor Collaboration, and Health Companion specialists) captured in [BACKLOG.md](../BACKLOG.md)'s Health Intelligence Cluster, elaborating Master Blueprint §15's already-named "Healthcare" direction. No PRD exists; this entry registers the number and direction only, exactly as CP-03 through CP-07 above do

### What CP-01 Establishes for Every Later Pack

CP-01 is not just first in sequence — it is the pack every later one is expected to build *on top of*, not merely alongside. It establishes the identity/goal/memory backbone (a durable model of who the user is, what they're working on, and what they've decided before) that CP-02 onward read from rather than re-deriving their own. See the PRD's §14 ("Future Expansion") for exactly what each later pack inherits.

This is a planning sequence, not a dependency order — packs are independent of each other (see Pack Independence, above), so this list may be reordered or extended without any pack depending on another having shipped first. `docs/00_OVERVIEW/Roadmap.md` should be treated as the living record of which packs are actually in progress or complete, and [CAPABILITY_READINESS.md](../CAPABILITY_READINESS.md) as the at-a-glance dashboard of each capability's current build maturity (Capability Readiness Level); this document is the strategy that governs how any of them get built, not a status tracker.

## What Changes and What Doesn't

| | Before M20.7 (architecture milestones) | After M20.7 (Capability Packs) |
|---|---|---|
| Unit of work | A milestone (`M16`, `M17`, ...) that could touch core frameworks | A pack (`CP-01`, `CP-02`, ...) that only ever registers into existing registries |
| Allowed to modify `BaseAgent`/`BaseTool`/`SharedExecutionContext`/etc.? | Yes, by design — the architecture was still being built | No — frozen, per [ARCHITECTURE_FREEZE_v1.md](../ARCHITECTURE_FREEZE_v1.md) |
| Where new code lives | Anywhere in `app/services/ai/` | New specialist/tool/provider modules, registered — never inside `shared/`, `kernel/`, `runtime/`'s own executor/registry/middleware code |
| What "done" means | Tests pass, docs updated, architecture consistent | Tests pass, docs updated, **and** the pack introduced zero changes to any frozen interface |

This is the same maturity transition every stable platform makes: the core stops changing, and everything of value from here forward is built as modular extensions on top of it.
