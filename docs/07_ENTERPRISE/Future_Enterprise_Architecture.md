# Future Enterprise Architecture

This document is explicitly forward-looking. Nothing here is implemented as of M19 — it describes how the platform's existing architecture is positioned to grow toward the enterprise vision described in [Vision.md](../00_OVERVIEW/Vision.md) and the project's own longer-range planning documents (`.ai/ROADMAP.md`, `.ai/ENTERPRISE_ROADMAP.md`). Every claim below is a projection based on what the current architecture makes possible, not a status report.

## Where the Current Architecture Already Points

The AI Operating System was built with enterprise growth in mind even though no enterprise-specific feature exists yet:

- **Provider swappability** (Conversation, Vision) means a client-mandated vendor, a cost-driven vendor swap, or a regulatory requirement to use a specific model provider is a registry registration, not a rewrite.
- **The Specialist Framework's registry-based extension model** means new business-domain agents (Finance, Business Architect) are additions, not modifications to the Executive or dispatcher.
- **Identity propagation** (`SharedExecutionContext`, `correlation_id`/`causation_id`) is already structural, not bolted on — this is the foundation an audit trail or compliance log would be built from, without needing an architectural change to add one.
- **Tenant scoping** already exists at the data layer (`organization_id`-scoped repositories, M11's "Per-Tenant Query Scoping") — `SharedExecutionContext.organization_id` is the same concept carried through the AI Operating System's execution identity, so a multi-tenant AI Operating System deployment is architecturally coherent with the rest of the platform, not a separate concern.

## Organization Operating Systems

The project's own `.ai/ROADMAP.md` describes Phase 5 ("Business Operating System") and Phase 6 ("Real Estate Operating System") — coordinated workflows for CRM, sales, marketing, procurement, reporting, and (for real estate specifically) development/investment/construction/facilities/compliance workflows. Architecturally, this maps onto the AI Operating System as: an Executive coordinating a broader roster of business-domain specialists (Finance, Business Architect, and domain-specific ones not yet named) against a broader tool catalog (CRM integrations, procurement systems, reporting tools) than exists today. None of this exists yet — the Executive/Specialist/Tool frameworks are the foundation this would be built on, not a partial implementation of it.

## Executive Dashboard

`.ai/ROADMAP.md` Phase 7 describes an executive workspace for daily/weekly/monthly reporting and strategic alerts. This would consume the AI Operating System's event streams (`RuntimeEvent`, `ExecutiveEvent`, `ResearchEvent`, etc. — see [Event_System.md](../02_KERNEL/Event_System.md)) as its data source, but no dashboard, no event persistence, and no aggregation layer exists today — every `EventPublisher` in this platform is in-process, synchronous, and has no subscriber that persists events anywhere.

## Governance and Human Oversight

`.ai/MISSION.md` states "automation must preserve human oversight where required." The Executive's `ExecutivePolicy` (`allow_web`, `allow_tools`, `allow_delegation`, `maximum_depth`) is the closest existing mechanism to a governance gate, but it is a static, code-configured policy object — there is no runtime approval workflow, no human-in-the-loop checkpoint, and no audit dashboard today. Building one would likely take the form of a new `KernelHook`/`RuntimeHook`/`AgentHook` implementation that pauses execution pending external approval — the hook mechanism already exists as the right extension point; the approval workflow itself does not.

## Compliance and Auditability

The identity model ([Identity_Model.md](../02_KERNEL/Identity_Model.md)) already gives every execution a reconstructable tree via `correlation_id`/`parent_execution_id`. What's missing for genuine auditability: durable event persistence (today, every `EventPublisher` loses its events the moment the process holding it exits — nothing writes them anywhere), and a policy layer that can *deny* an execution before it starts based on compliance rules, not just observe it afterward.

## Self-Improving AI

Every planner in the platform today (`ExecutivePlanner`, `SpecialistPlanner`, `ResearchPlanner`) is deterministic and template-based — none evaluates its own past performance or adjusts its behavior. A genuine self-improvement loop would need, at minimum: durable outcome tracking (did this plan succeed?), a feedback mechanism back into planning, and almost certainly a new Kernel-level or Executive-level capability that doesn't exist in any form today, not even as a declared contract. This is the most speculative item in this document — treat it as a direction, not a near-term project.

## Enterprise Deployment

`.ai/ROADMAP.md` Phase 10 covers secure production deployment, monitoring, scaling, resilience, and auditing. As of M19, deployment tooling in this repository is limited to a `Dockerfile`; no monitoring/observability stack, no horizontal-scaling design for the AI Operating System specifically (e.g. how `EventPublisher` subscribers or in-process registries behave across multiple worker processes), and no production-hardening pass has been done. This is real, unaddressed work, not an oversight to be quietly assumed away — a multi-process deployment today would mean each process has its own independent, in-memory provider/tool/agent registries, which is a correctness question worth resolving deliberately before relying on it.

## What This Document Is Not

This is not a commitment or a project plan — no dates, owners, or sequencing are implied. It exists so a reader (human or AI) evaluating "is this platform enterprise-ready" can see both what the current architecture already supports and what is genuinely still open, without either overselling the current state or underselling the foundation that's actually there.
