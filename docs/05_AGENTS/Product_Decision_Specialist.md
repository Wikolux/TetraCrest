# Product Decision Specialist

`ProductDecisionSpecialist` (CP-02, Milestone 4) is CP-02's second specialist — see [Product_Management_Intelligence.md](../04_CAPABILITIES/Product_Management_Intelligence.md) for the pack-level guide this document sits under. It converts validated Discovery evidence into structured, framework-applied product decisions with a mandatory counterpoint step — never a decision presented as more certain than its evidence and reasoning actually support.

This document contains no implementation detail and no code.

## Purpose

Product Decision answers: **given the evidence, what should we do, using a named framework, and what's the case against it?** It is the direct product-domain specialization of decision-support discipline — apply a real framework, surface a real counterpoint, and never decide silently.

## Responsibilities

Per PRD §12/Architecture §8: feature prioritization, framework selection and application (RICE, ICE, Kano, Cost of Delay/WSJF, build-vs-buy comparison, sunset checklist — six frameworks, never a seventh invented ad hoc), trade-off analysis, option comparison, risk identification, assumption validation, confidence assessment, and evidence-backed recommendation generation with a required counterpoint. As a byproduct, it also tracks which frameworks were applied and with what rigor over time (the PM Craft Record), feeding CP-01's own Career Development journey without building a dedicated career-coaching mode itself.

## Operations

Ten: prioritize features, apply a named framework, analyze trade-offs, compare options, identify risks, validate assumptions, assess confidence, generate an evidence-backed recommendation (with mandatory counterpoint), summarize a decision, and recall decision history in bulk.

## Inputs

A decision question, the framework to apply (or enough context to select one), options being compared, criteria, stated assumptions, and — read automatically — prior Discovery Findings, Research Findings, and Decision Records relevant to the question.

## Outputs

A `DecisionRecord` (title, framework applied, rationale, and — when known later — outcome) for `GENERATE_RECOMMENDATION`; a `PMCraftRecord` byproduct write alongside it; synthesized, framework-explained responses for every other operation, whether or not they write a durable record.

## Memory Usage

Owns and writes **Decision Record** (`product_decision`) and **PM Craft Record** (`product_pm_craft_record`, a byproduct of Decision Support, feeding Career Development). Reads Discovery Findings and Research Findings the same way every consumer does — through `ProfessionalMemoryService.recall()`, organization-scoped and semantic, never a direct import of Discovery's own code or types. Every write is append-only: an outcome recorded later is a new entry referencing the original decision, never an edit to it.

## Evidence Discipline

`DecisionRecord` cannot be constructed without evidence or an explicit evidence gap, non-empty assumptions/risks/trade-offs, a stated expected impact, and a stated remaining uncertainty — a structurally enforced guarantee (ARR §7), not a documented convention. The counterpoint step is not optional: a recommendation without a surfaced counterpoint is incomplete by this specialist's own definition. When no evidence is retrieved, `GENERATE_RECOMMENDATION` never writes a `DecisionRecord` at all — it honestly recommends further Discovery instead.

## Executive Interaction

Declares `AgentCapability.REASONING`/`PLANNING` only — never `MEMORY`, for the same Executive collision-avoidance reason every CP-02 specialist follows. Every `DecisionRecord` it writes becomes evidence Strategy & Portfolio and Stakeholder Communication can read, and every PM Craft Record becomes input to CP-01's Career Development, all through shared memory, never a direct call between specialists or packs.

## Typical Workflow

Discovery Findings accumulate → a PM asks Product Decision to apply a framework to a candidate feature or trade-off → the specialist retrieves the relevant evidence, applies the named framework, surfaces a counterpoint, and either writes a `DecisionRecord` (evidence sufficient) or honestly recommends more Discovery first (evidence thin) → the resulting `DecisionRecord` becomes precedent for Strategy's roadmap sequencing and Stakeholder Communication's "why" narratives.

## Extension Guidance

See [Adding_Product_Management_Specialists.md](../06_DEVELOPMENT/Adding_Product_Management_Specialists.md). A new decision framework is the most likely extension here — it's an addition to `scoring.py`'s own framework-selection logic and the `DecisionFramework` enum, not a new specialist or new memory category, provided it fits the existing "framework applied + counterpoint + evidence" shape every decision already follows.

## Limitations

Framework selection is deterministic (a fixed decision-shape-to-framework mapping), not adaptive or learned. "Opportunity scoring" reuses `PRIORITIZE_FEATURES` against an opportunity-shaped input rather than a dedicated operation, since opportunity assessment itself remains Discovery's own responsibility, never recreated here. No cross-product prioritization — that is Strategy & Portfolio's own, deliberately dormant, extension point.
