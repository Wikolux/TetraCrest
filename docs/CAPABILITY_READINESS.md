# AI Operating System — Capability Readiness Dashboard

| | |
|---|---|
| **Status** | Living document — updated after every major milestone, per [VERSION_1_DEVELOPMENT_GUIDE.md](VERSION_1_DEVELOPMENT_GUIDE.md) |
| **Authority** | An operational tracking document, not a governance document — it reports status against the standards [MASTER_BLUEPRINT.md](MASTER_BLUEPRINT.md), [PRODUCT_PHILOSOPHY_FREEZE_v1.md](PRODUCT_PHILOSOPHY_FREEZE_v1.md), [ARCHITECTURE_FREEZE_v1.md](ARCHITECTURE_FREEZE_v1.md), and the [Version 1 Development Guide](VERSION_1_DEVELOPMENT_GUIDE.md) already set; it does not itself set new standards or outrank any of them |
| **Complements** | [Roadmap.md](00_OVERVIEW/Roadmap.md) (chronological milestone history) and [Capability_Strategy.md](08_CAPABILITY_PACKS/Capability_Strategy.md) (pack strategy and numbering) — this document is the at-a-glance, per-capability status view; it does not replace either |
| **Last updated** | CP-02 Milestone 10 (Release Candidate & Capability Freeze) complete — CP-02 Version 1 released |

## Introduction

This dashboard answers one question for any capability on this platform, in under a minute: **how ready is it, really?** Not "does it exist in the vision" (the Master Blueprint already answers that, expansively) and not "what happened, chronologically" (the Roadmap already answers that) — specifically, precisely, how far along its own lifecycle a given capability actually is today, what stands between it and its next milestone, and what risks are already known.

## Purpose

As the platform grows from two Capability Packs toward the dozens the Master Blueprint envisions, no single person will hold the state of every capability in their head. This dashboard exists so that question never has to be reconstructed from memory, commit history, or a dozen scattered documents — it is read first, before deciding what to build next, and updated every time a milestone closes.

## Capability Readiness Level (CRL)

**A note on the name before the definition**: "CRL" is already used elsewhere in this platform's documentation for a *different* concept — the **Companion Readiness Level** introduced in [CP-01's Insight Engine documentation](08_CAPABILITY_PACKS/CP-01_Personal_Intelligence_Pack/Implementation_Insight_Engine.md) (CRL-1 through CRL-4+), which measures how personal and proactive the *platform's overall companion behavior* has become — a philosophical, product-experience axis. The **Capability Readiness Level** defined below measures something narrower and more operational: for *one named capability*, how far it has progressed through the [Version 1 Development Guide](VERSION_1_DEVELOPMENT_GUIDE.md)'s own nine-phase lifecycle. The two scales are deliberately not merged — one describes what the platform *feels like* to use; this one describes what engineering work is *actually done*. Where both apply to the same capability (as they do for CP-01), they are cited separately, never conflated.

### CRL Scale (0–5)

| CRL | Name | Meaning | Development Guide phases complete |
|---|---|---|---|
| **CRL-0** | Not Started | Named as a future direction (typically in the Master Blueprint's own vision) but no Product Requirements Document exists yet. | None |
| **CRL-1** | Specified | A Product Requirements Document is complete and approved. | Phase 1 |
| **CRL-2** | Architected | Engineering Architecture is complete, and an Architecture Readiness Review has returned a formal verdict (READY, READY WITH CONDITIONS, or NOT READY). | Phases 1–2.5 |
| **CRL-3** | Building | An Implementation Plan is complete, and production implementation is underway (at least one milestone shipped, not all). | Phases 1–3, Phase 4 in progress |
| **CRL-4** | Verified | Implementation, Verification, Documentation, and Integration Validation are all complete. Not yet released. | Phases 1–7 |
| **CRL-5** | Released | A Release Candidate has passed every gate and the capability is formally released — tracked as shipped in `Roadmap.md`. | Phases 1–9 |

A capability's CRL is never advanced by intention, estimate, or partial credit — it reflects only phases actually completed, verified the same way this dashboard's own entries below were checked against real test counts and real documents, not against plans for them.

## Current Platform Assessment

### Platform Infrastructure & Frameworks

| Field | Value |
|---|---|
| **Name** | Platform Infrastructure (Shared substrate, Kernel) |
| **Current CRL** | CRL-5 — Released |
| **Status** | Frozen at v1.0 ([ARCHITECTURE_FREEZE_v1.md](ARCHITECTURE_FREEZE_v1.md)). `GenericProviderRegistry`/`GenericEvent`/`GenericMiddleware` (ADR-0002) fully consolidated; Kernel remains an intentional contract-only foundation (`KernelRuntime.execute()` unimplemented by design). |
| **Owner Pack** | None — platform-owned, not a Capability Pack |
| **Dependencies** | None (the platform's own foundation) |
| **Blocking Items** | None |
| **Next Milestone** | None planned — frozen |
| **Known Risks** | Kernel/Runtime duality remains named, accepted technical debt (Architecture Freeze §"Remaining Technical Debt") |
| **Version Target** | v1.0 (shipped) |

| Field | Value |
|---|---|
| **Name** | Runtime |
| **Current CRL** | CRL-5 — Released |
| **Status** | Fully working, provider-agnostic conversational execution engine. |
| **Owner Pack** | None — platform-owned |
| **Dependencies** | Shared substrate, Conversation Framework |
| **Blocking Items** | None |
| **Next Milestone** | None planned — frozen |
| **Known Risks** | None currently tracked |
| **Version Target** | v1.0 (shipped) |

| Field | Value |
|---|---|
| **Name** | Memory Framework (`AgentMemory`/`MemoryAdapter`/`AIMemoryService`/`MemoryRetrievalPipeline`) |
| **Current CRL** | CRL-5 — Released |
| **Status** | All four `AgentMemory` methods (`remember`/`retrieve`/`forget`/`search`) fully implemented since CP-01.2, closing the platform's one historically-blocking gap. |
| **Owner Pack** | None — platform-owned; consumed by every Capability Pack |
| **Dependencies** | Shared substrate, Retrieval Pipeline, embedding/vector-store layer |
| **Blocking Items** | None |
| **Next Milestone** | None planned — frozen |
| **Known Risks** | `memory_type` remains an unenforced string convention, not a validated taxonomy (accepted debt, CP-01 Architecture §19); see ADR-0006 for the governing discipline on when a new `memory_type` is warranted |
| **Version Target** | v1.0 (shipped) |

| Field | Value |
|---|---|
| **Name** | Executive Framework |
| **Current CRL** | CRL-5 — Released |
| **Status** | Capability-based dispatch, `TaskGraph`, `ExecutivePlanner` all fully working and proven across three independently-built specialists with zero collisions. |
| **Owner Pack** | None — platform-owned |
| **Dependencies** | Shared substrate, Agent Framework |
| **Blocking Items** | None |
| **Next Milestone** | None planned — frozen |
| **Known Risks** | `ExecutivePlanner`'s deterministic template does not yet exercise single-plan, multi-specialist delegation (CP-02 Architecture §9/§20) — a documented, non-blocking open question, not a defect |
| **Version Target** | v1.0 (shipped) |

| Field | Value |
|---|---|
| **Name** | Specialist Framework |
| **Current CRL** | CRL-5 — Released |
| **Status** | `SpecialistAgent` contract, registries, coordinator, and adapters fully stable — the platform's primary Capability Pack extension point. |
| **Owner Pack** | None — platform-owned |
| **Dependencies** | Agent Framework, Executive Framework |
| **Blocking Items** | None |
| **Next Milestone** | None planned — frozen |
| **Known Risks** | `SpecialistDispatcher.dispatch_by_specialization()` has no production caller (accepted debt) |
| **Version Target** | v1.0 (shipped) |

| Field | Value |
|---|---|
| **Name** | Tool Framework |
| **Current CRL** | CRL-5 — Released (as scoped) |
| **Status** | Contract, registry, factory, and execution engine fully complete. First concrete tool (`WikipediaSearchTool`, read-only, `ToolCategory.SEARCH`) implemented and registered as of P7.15, proven end-to-end through `ToolDiscovery → ToolRegistry → ToolExecutor → WikipediaSearchTool` under a real, non-fail-open `PermissionPolicy` requiring `ToolPermission.NETWORK`. `ToolExecutor`'s own shared `permission_policy=None` default is deliberately unchanged — P7.15's own production composition (the `/api/v1/research/lookup` route) is the one place that always supplies a real policy; every other concrete tool remains unregistered. |
| **Owner Pack** | None — platform-owned |
| **Dependencies** | Shared substrate, Runtime |
| **Blocking Items** | Write-capable tools remain blocked from production use until idempotency/duplicate-execution protection and consequential-action authority (`AutonomyGrant`) are designed for that tier — not needed for the read-only tool shipped in P7.15 |
| **Next Milestone** | A second concrete tool, ideally a write-capable one, to prove the deferred idempotency/autonomy questions for real (unscheduled) |
| **Known Risks** | None to the framework itself; the fixed `PermissionPolicy` P7.15's route grants is an application-level capability policy, not general user/role authorization — no RBAC/ABAC source exists yet |
| **Version Target** | v1.0 (framework shipped); first concrete tool shipped P7.15 |

| Field | Value |
|---|---|
| **Name** | Execution Ledger |
| **Current CRL** | CRL-3 — Minimal, scoped implementation (not a general recovery platform) |
| **Status** | First durable, pre-commit operational execution record shipped P7.16: `ExecutionRecord` (`execution_records` table) is written `STARTED` and committed before either external call in `/api/v1/research/lookup` (Wikipedia, OpenAI) is attempted, then updated to exactly one immutable terminal status (`SUCCEEDED`/`FAILED`). A record left at `STARTED` after an interruption is the intentional, honest signal that no terminal outcome was durably recorded — it does not itself prove or disprove that an external side effect occurred. Deliberately separate from `AuditLog` (supplementary, historical, write-once provenance, now carrying the same `execution_id`/`correlation_id` in its `details`) — `ExecutionRecord` is the one place holding *current* operational state. |
| **Owner Pack** | None — platform-owned |
| **Dependencies** | Shared substrate (`SharedExecutionContext`), Tool Framework, Runtime |
| **Blocking Items** | No idempotency enforcement, no retry-safety guarantee, and no automatic recovery/reconciliation exist yet — `list_non_terminal()` makes stranded records discoverable, but nothing acts on them. All three remain explicit prerequisites for any write-capable tool. |
| **Next Milestone** | Unscheduled — candidates are idempotency keys, a reconciliation/recovery consumer of `list_non_terminal()`, or richer per-attempt (not just root-execution) provenance |
| **Known Risks** | A failure to commit a terminal update or an audit row must never (and, per P7.16's own tests, does not) discard an already-produced successful result from reaching the client — proven directly, not merely asserted |
| **Version Target** | v1.0 scope; first durable execution record shipped P7.16 |

| Field | Value |
|---|---|
| **Name** | Vision Framework |
| **Current CRL** | CRL-5 — Released (as scoped) |
| **Status** | Contract, four capability services, runtime/executor fully complete (ADR-0005). Zero concrete providers registered — intentional. |
| **Owner Pack** | None — platform-owned |
| **Dependencies** | Shared substrate, Runtime |
| **Blocking Items** | A concrete Vision provider does not yet exist — blocks CP-01 Knowledge Intelligence's and CP-02 Discovery's Vision-assisted capture journeys, not the framework itself |
| **Next Milestone** | First concrete Vision provider (unscheduled) |
| **Known Risks** | None to the framework itself |
| **Version Target** | v1.0 (framework shipped); first concrete provider unscheduled |

| Field | Value |
|---|---|
| **Name** | Conversation Framework |
| **Current CRL** | CRL-5 — Released (as scoped) |
| **Status** | Provider-agnostic contract, registry, factory fully complete. First concrete vendor provider (OpenAI, Chat Completions) implemented and registered as of P7.14 — proven end-to-end through RuntimeAdapter → AIRuntime → RuntimeExecutor → ConversationProviderFactory → ConversationProviderRegistry → OpenAIConversationProvider, and into an existing, unmodified Personal OS narration path. Every other vendor (Anthropic, Gemini, Ollama, OpenRouter, DeepSeek, Qwen, Mistral, Grok) remains unregistered — matching Tool and Vision's own "framework complete, additional concrete providers unscheduled" state. |
| **Owner Pack** | None — platform-owned |
| **Dependencies** | Shared substrate |
| **Blocking Items** | None for a single-provider (OpenAI) real-model path; a second vendor provider does not yet exist — does not block real-world generation, only provider choice/failover |
| **Next Milestone** | Second concrete provider (unscheduled); real tool execution (see Personal OS/Roadmap for the P7.13 gap audit this follows) |
| **Known Risks** | Single-vendor dependency; no cross-provider failover exists yet (deliberately out of P7.14's scope) |
| **Version Target** | v1.0 (framework shipped); first concrete provider shipped P7.14 |

| Field | Value |
|---|---|
| **Name** | Research (`ResearchAgent`) |
| **Current CRL** | CRL-5 — Released |
| **Status** | The platform's first concrete specialist (M18) and the reference implementation every later specialist, including all of CP-02's planned specialists, pattern-matches against. Reused by CP-02 via delegation (Architecture §9), never duplicated. |
| **Owner Pack** | None — platform-owned specialist, consumed by every pack |
| **Dependencies** | Specialist Framework, Executive Framework |
| **Blocking Items** | None |
| **Next Milestone** | A dedicated Research Intelligence Capability Pack (Master Blueprint §15) would mature this into a full professional research discipline — CRL-0, unstarted |
| **Known Risks** | None currently tracked |
| **Version Target** | v1.0 (shipped) |

| Field | Value |
|---|---|
| **Name** | Personal OS (Application Layer) |
| **Current CRL** | CRL-3 — Building (calibration note: Personal OS follows its own numbered build-spec process, not the Capability Pack Development Guide's exact nine phases — this CRL is reported by analogy, not by a formal Architecture Readiness Review or Release Candidate gate) |
| **Status** | An Application, not a Capability Pack (registers no `SpecialistAgent`, declares no `AgentCapability`, mints no Memory Framework namespace — architecturally enforced, `test_personal_os_architecture.py`). P1 through P7.16 built a complete, tested daily-operating-system domain model (Daily Intent, Personal State, Adaptive Planning, Intelligence Brief, Evening Reflection, Pattern Intelligence, Experimentation, Life Domains, Missions, Living Day event log, Continuous Replanning, Conversational Day Interaction, Controlled Adaptation, Runtime Adaptation, Outcome Measurement) with real SQL-backed persistence throughout, entirely reachable only through direct Python calls until P7.17. **P7.17 shipped Personal OS's first production API surface** — five authenticated HTTP endpoints (`GET /today`, `POST /today/intent`, `POST /today/interact`, `POST /today/reflect`, `GET /brief`) exposing the daily lifecycle end to end, composing the existing flows with zero new Personal OS intelligence. **P7.18 shipped the human-governance surface** — five further endpoints (`GET /decisions`, `GET /decisions/{entity_type}/{entity_id}`, `POST /patterns/{id}/respond`, `POST /experiments/{id}/respond`, `POST /adaptations/{id}/respond`) letting an authenticated user see and act on already-pending Pattern/Experiment/Adaptation decisions through the exact authoritative flow methods those flows already defined — previously the only way any of that intelligence was ever triggered by a real human decision was a test fixture calling a flow method directly. |
| **Owner Pack** | None — platform-owned Application |
| **Dependencies** | RuntimeAdapter/AIRuntime (narration only, via the sanctioned seam every specialist also uses), AgentMemory (Personal State's own read path) |
| **Blocking Items** | Per-user timezone support does not exist (P7.17's `resolve_personal_os_today()` assumes a single UTC calendar date for every user); no upstream orchestration exists anywhere on this platform to call `PatternDetectionFlow.surface_next()`, `ExperimentRepository.list_ready_for_review()`, or `ExperimentFlow.review()` in production, so a freshly-detected `OBSERVED` Pattern or a past-review-date `ACTIVE` Experiment never actually reaches P7.18's own decision list until a future milestone builds that caller; Mission/LifeDomain CRUD remains unexposed (no application-flow boundary exists yet for either) |
| **Next Milestone** | Building the upstream orchestration that actually surfaces `OBSERVED` patterns and promotes due experiments to review — without it, P7.18's governance surface can only ever act on decisions some other caller (today, only a test) already produced |
| **Known Risks** | `SqlDayEventRepository.append()`'s read-then-insert sequence assignment is guarded by a database uniqueness constraint (P7.17) but not by real concurrency control (no lock, no retry) — acceptable for a single-human-operating-their-own-day product, not for high-concurrency multi-writer use. `PatternRecord` has no id-based lookup independent of status (every `respond()` call is a brand-new row) — a repeated action against the same `pattern_id` 404s rather than 409s, unlike Experiment/Adaptation's own stable-id-backed 409 (P7.18, documented deviation, not corrective) |
| **Version Target** | Daily-lifecycle API shipped (P7.17); governance/decisions API shipped (P7.18); upstream surfacing orchestration unscheduled |

### Capability Packs

| Field | Value |
|---|---|
| **Name** | Personal Intelligence (CP-01) |
| **Current CRL** | CRL-5 — Released |
| **Status** | Phases 1–4 all complete: Identity, Goal, Project, Reflection, Preference Intelligence, and the Insight Engine (CP-01.3) — the platform's proof its foundation holds real weight. |
| **Owner Pack** | CP-01 |
| **Dependencies** | Memory Framework, Executive Framework, Specialist Framework |
| **Blocking Items** | None |
| **Next Milestone** | Decision/Learning/Communication/Business/Productivity/Relationship/Knowledge/Life Intelligence (Architecture §3) remain deferred, out of scope for the current release |
| **Known Risks** | Echo-chamber effect (mitigated, CP-01 Guiding Principle 7); retrieval quality inherited from, not controlled by, the platform's embedding/ranking layer |
| **Version Target** | v1.0 (shipped) |

| Field | Value |
|---|---|
| **Name** | Insight Engine (CP-01.3, Executive Cognition) |
| **Current CRL** | CRL-5 — Released |
| **Status** | Deterministic pattern/habit/contradiction/alignment detection, periodic reflections, proactive recommendations, and an evolving profile — every insight traceable to its source memories. Moved the platform from Companion Readiness Level CRL-2 toward CRL-3 (the *other* CRL scale — see disambiguation, above). |
| **Owner Pack** | CP-01 |
| **Dependencies** | Personal Intelligence (CP-01 core), Memory Framework |
| **Blocking Items** | None |
| **Next Milestone** | No wall-clock/cron trigger for periodic reflections yet (capability exists; nothing schedules it automatically) |
| **Known Risks** | Detection heuristics are intentionally coarse (no stemming/synonym awareness) — documented, not hidden |
| **Version Target** | v1.0 (shipped) |

| Field | Value |
|---|---|
| **Name** | Product Management Intelligence (CP-02) |
| **Current CRL** | CRL-5 — Released |
| **Status** | All ten implementation milestones complete. All five specialists (Discovery, Product Decision, Delivery, Strategy & Portfolio, Stakeholder Communication) implemented, integration-validated against the Executive, and fully documented. Every ARR §15 condition resolved; both findings the Milestone 9 Production Readiness Report left open are closed (Milestone 10). Version 1 frozen — see [CP-02_RELEASE_CANDIDATE.md](08_CAPABILITY_PACKS/CP-02_Product_Management_Intelligence_Pack/CP-02_RELEASE_CANDIDATE.md). |
| **Owner Pack** | CP-02 |
| **Dependencies** | Personal Intelligence (CP-01, read-only, via shared memory — never direct import, ADR-0006 and CP-02 Architecture §19), Memory Framework, Executive Framework, Research (delegated) |
| **Blocking Items** | None |
| **Next Milestone** | None against this version — frozen. Real cross-product Portfolio Intelligence, tool-integrated Delivery journeys, and single-plan multi-specialist Research delegation are named future extension points (Product_Management_Intelligence.md), reachable through Version 2 or a future Capability Pack, not this version. |
| **Known Risks** | Single-plan multi-specialist Research delegation remains an open, non-blocking Executive Framework question (Architecture §9/§20); framework misapplication risk mitigated by Architecture §8's structural framework-selection discipline; no production `ExecutiveAgent` deployment yet delegates a rich, operation-specific request to any CP-02 specialist (a platform-level `ExecutivePlanner` limitation shared with CP-01, not a CP-02 defect) |
| **Version Target** | v1.0 (shipped) |

### Future Capability Packs (Vision-Stage, CRL-0)

The fifteen packs below are named in [MASTER_BLUEPRINT.md](MASTER_BLUEPRINT.md) §15 as the platform's envisioned direction — not a committed schedule (Master Blueprint's own words: "not a committed schedule, and not a final numbering"). None has a PRD. Each is CRL-0 by definition until one exists. Dependencies, blocking items, and risk are identical across this group (no Phase 1 has begun) and are therefore stated once rather than repeated fifteen times.

**Common to every row below**: Dependencies — Personal Intelligence (CP-01), per the "professional intelligence builds on personal intelligence" pattern CP-02 established (Master Blueprint §14). Blocking items — no Product Requirements Document exists; Phase 1 has not begun. Known risks — none yet assessable at CRL-0; risk assessment begins at Phase 2.5 (Architecture Readiness Review) per the Development Guide.

| Name | Current CRL | Status | Next Milestone | Version Target |
|---|---|---|---|---|
| Finance Intelligence | CRL-0 | Named in Master Blueprint §15; also CP-03 in `Capability_Strategy.md`'s numbering sequence | Phase 1 — PRD | Unscheduled |
| Trading Intelligence | CRL-0 | Named in Master Blueprint §15; also CP-04 in `Capability_Strategy.md`'s numbering sequence | Phase 1 — PRD | Unscheduled |
| Legal Intelligence | CRL-0 | Named in Master Blueprint §15 | Phase 1 — PRD | Unscheduled |
| Marketing Intelligence | CRL-0 | Named in Master Blueprint §15; also CP-06 in `Capability_Strategy.md`'s numbering sequence | Phase 1 — PRD | Unscheduled |
| Coding / Developer Intelligence | CRL-0 | Named in Master Blueprint §15 (as "Coding"); also CP-05 ("Software Engineering") in `Capability_Strategy.md`'s numbering sequence | Phase 1 — PRD | Unscheduled |
| Research Intelligence (dedicated pack) | CRL-0 | Named in Master Blueprint §15 as the future *maturation* of the already-shipped `ResearchAgent` specialist (itself CRL-5) into a full professional discipline — the specialist and the future pack are tracked separately, above and here respectively | Phase 1 — PRD | Unscheduled |
| Healthcare Intelligence (Health Intelligence Pack) | CRL-0 | Named in Master Blueprint §15; also CP-08 in `Capability_Strategy.md`'s numbering sequence — elaborated as a lifelong health companion (Health Profile, Wellness, Nutrition, Emergency Response, Doctor Collaboration, Health Companion specialists) in [BACKLOG.md](BACKLOG.md)'s Health Intelligence Cluster | Phase 1 — PRD | Unscheduled |
| Education Intelligence | CRL-0 | Named in Master Blueprint §15 | Phase 1 — PRD | Unscheduled |
| Enterprise Operating System | CRL-0 | Named in Master Blueprint §15; also CP-07 in `Capability_Strategy.md`'s numbering sequence; direction further recorded in `Future_Enterprise_Architecture.md` | Phase 1 — PRD | Unscheduled |
| Sales Intelligence | CRL-0 | Named in Master Blueprint §15 | Phase 1 — PRD | Unscheduled |
| Real Estate Intelligence | CRL-0 | Named in Master Blueprint §15 | Phase 1 — PRD | Unscheduled |
| Relationship Intelligence (dedicated pack) | CRL-0 | Named in Master Blueprint §15, distinct from CP-01's own lightweight relationship tracking | Phase 1 — PRD | Unscheduled |
| Language Intelligence | CRL-0 | Named in Master Blueprint §15 as the concrete product home for the platform-wide Universal Language Philosophy (Master Blueprint §17, Product Philosophy Freeze §7) | Phase 1 — PRD | Unscheduled |
| Creative Intelligence | CRL-0 | Named in Master Blueprint §15 | Phase 1 — PRD | Unscheduled |
| Operations Intelligence | CRL-0 | Named in Master Blueprint §15 | Phase 1 — PRD | Unscheduled |

**A note on completeness, in the interest of not overstating the roadmap**: "Meeting Intelligence" and an agriculture-specific capability were considered for this dashboard but are **not** currently named future packs anywhere in `Capability_Strategy.md` or Master Blueprint §15. Including them here as roadmap rows would itself be a stale/invented reference — exactly what this dashboard's own governance discipline exists to avoid. Their vision is captured honestly, at the idea stage, in [BACKLOG.md](BACKLOG.md) instead, where they belong until a PRD is written.

## How This Dashboard Is Maintained

Every Capability Pack's Development Guide Phase 9 (Capability Release) checklist includes updating this dashboard, alongside `Roadmap.md` and `Capability_Strategy.md`. A capability's CRL is updated the moment the phase that earns it is actually complete — never in advance, and never left stale after a phase closes.
