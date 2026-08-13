# Delivery Specialist

`DeliverySpecialist` (CP-02, Milestone 5) is CP-02's third specialist — see [Product_Management_Intelligence.md](../04_CAPABILITIES/Product_Management_Intelligence.md) for the pack-level guide this document sits under. It turns already-validated discovery evidence and already-decided product decisions into drafted delivery artifacts — the PM's own side of shipping, never the engineering team's execution.

This document contains no implementation detail and no code.

## Purpose

Delivery answers: **given what we've validated and decided, what does the PM-facing side of "getting it built and shipped" actually require?** PRD/spec drafting, story structuring, acceptance criteria, cross-functional coordination artifacts, and launch-readiness checks — always grounded in prior evidence, never invented from a bare feature name.

## Responsibilities

Per PRD §16: PRD/spec drafting, user story structuring, acceptance criteria, cross-functional coordination artifacts (RACI-style framing, engineering-facing status), and launch readiness — plus the PM-facing side of sprint/release cadence awareness only (ARR §9: "never engineering-side ceremony execution"). Delivery never re-prioritizes by business value (that remains Product Decision's own responsibility) and never invents a team's capacity or velocity — those figures are always caller-supplied.

## Operations

Thirteen: plan a sprint (PM-facing framing only), refine the backlog (evidence-grounded readiness only, never re-prioritization), decompose a story, break down an epic, generate acceptance criteria, detect delivery risks, analyze dependencies, generate an evidence-backed recommendation, support an engineering handoff, summarize delivery state, support a retrospective, check launch readiness, and recall prior delivery work.

## Inputs

A feature or epic description, acceptance-criteria items, dependencies, caller-supplied capacity/planned-load figures when relevant, and — read automatically — Discovery Findings, Research Findings, Decision Records, and PM Craft Records relevant to the work.

## Outputs

A `DeliveryArtifact` (one of: `SPEC`, `USER_STORY`, `ACCEPTANCE_CRITERIA`, `LAUNCH_READINESS`, `HANDOFF_NOTE`, `RETROSPECTIVE`, `RECOMMENDATION`) for every drafting operation with sufficient evidence; a `FeatureInitiative` stage-transition write when a recommendation names a delivery stage; a Delivery Confidence Score (a deterministic fraction of concrete, checkable factors — never a model-guessed number) on every major recommendation and launch-readiness check.

## Memory Usage

Owns and writes **Delivery Artifact** (`product_delivery_artifact`) and **Feature/Initiative** stage transitions (`product_feature`). Reads Discovery Findings, Research Findings, Decision Records, and PM Craft Records the same way every consumer does — through `ProfessionalMemoryService.recall()`, never a direct import of Discovery's or Product Decision's own code. Every artifact write is append-only: a revision is a new draft entry, never an edit to a prior one.

## Evidence Discipline

`DeliveryArtifact` cannot be constructed without both `linked_evidence_ids` and a `feature_title` — a structurally enforced guarantee (ARR §6, Architecture §14), not a documented convention. When no evidence is retrieved, every drafting operation (acceptance criteria, engineering handoff, story decomposition, epic breakdown, launch readiness, recommendation generation) declines to write an artifact and honestly recommends further Discovery or Decision Support instead — it still synthesizes a response explaining the gap, it just doesn't persist a record it can't ground.

## Executive Interaction

Declares `AgentCapability.REASONING`/`PLANNING` only — never `MEMORY`. Delivery Artifacts it writes are the evidence Stakeholder Communication drafts status updates from, and Feature/Initiative stage transitions are read by Strategy & Portfolio — both exclusively through shared memory.

## Typical Workflow

A Discovery Finding is validated and a Decision Record approves a direction → a PM asks Delivery to draft acceptance criteria, decompose stories, or check launch readiness → Delivery retrieves the grounding evidence and either drafts and persists the artifact (evidence sufficient) or honestly declines with a specific gap named (evidence thin) → the resulting artifacts become what Stakeholder Communication later drafts status updates from.

## Extension Guidance

See [Adding_Product_Management_Specialists.md](../06_DEVELOPMENT/Adding_Product_Management_Specialists.md). Tool-integrated journeys (issue-tracker/project-management read-write, once a concrete Tool provider exists platform-wide) are this specialist's most likely next extension — via `ToolManager`, never a direct integration, matching CP-01's own "Productivity Intelligence integrates via `ToolManager`, once tools exist" posture.

## Limitations

No tool-integrated journeys yet — depends on a concrete Tool provider that doesn't exist platform-wide. Sprint/release cadence awareness is PM-facing framing only, never engineering-side ceremony execution, by explicit PRD non-goal. Capacity and planned-load figures are always caller-supplied — Delivery never estimates or invents them.
