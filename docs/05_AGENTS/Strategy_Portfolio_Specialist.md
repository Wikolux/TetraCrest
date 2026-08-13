# Strategy & Portfolio Specialist

`StrategyPortfolioSpecialist` (CP-02, Milestone 6) is CP-02's fourth specialist — see [Product_Management_Intelligence.md](../04_CAPABILITIES/Product_Management_Intelligence.md) for the pack-level guide this document sits under. It is the pack's forward-looking, sequencing-and-prioritization specialist, built at single-product scope, with cross-product Portfolio reasoning present only as a named, honestly-scoped, dormant extension point.

This document contains no implementation detail and no code.

## Purpose

Strategy & Portfolio answers: **given what we know, what's the sequence, and what does the goal state look like?** Roadmap construction, backlog-level prioritization, and OKR/North Star Metric structuring — grounded in captured evidence and prior decisions, never generic goal-setting advice.

## Responsibilities

Per PRD §17: roadmap construction and sequencing, backlog-wide prioritization-framework application (RICE, ICE, Kano, Cost of Delay/WSJF — the same six-framework catalogue Product Decision uses, applied at the roadmap level rather than to a single decision), and OKR/North Star Metric structuring. Portfolio Intelligence (PRD §19) is a defined, dormant extension within this specialist, not working cross-product functionality — see Limitations.

## Operations

Eleven: sequence the roadmap, prioritize initiatives, compare opportunities, assess vision alignment, structure a North Star Metric, structure OKRs, assess trade-offs, generate an evidence-backed recommendation, assess the portfolio (single-product-inventory only), summarize strategy, and recall prior strategic work.

## Inputs

A set of candidate initiatives, prioritization criteria, OKR/North Star inputs, named products for portfolio assessment, and — read automatically — Decision Records, Discovery Findings, and Delivery Artifacts relevant to the sequencing question.

## Outputs

A `RoadmapItem` or `Metric` write for sequencing/structuring operations with sufficient evidence; a `StrategyRecommendation` (evidence-backed, no `counterpoint` field — that discipline remains exclusively Product Decision's own) for recommendation generation; a `PortfolioAssessment` (always carrying a mandatory scope note) for portfolio-scoped requests.

## Memory Usage

Owns and writes **Roadmap State** (`product_roadmap`, also where Portfolio-level views are recorded — no separate `product_portfolio` category exists, ADR-0006) and **Metric / North Star Record** (`product_metric`). Reads Decision Records, Discovery Findings, and Delivery Artifacts through `ProfessionalMemoryService.recall()`, never a direct import of another specialist's code. Never writes a `DecisionRecord` or `DeliveryArtifact` — each remains its own specialist's exclusive surface. Every write is append-only: a roadmap revision is a new entry referencing the prior state, never an edit.

## Evidence Discipline

`StrategyRecommendation` cannot be constructed without evidence or an explicit gap, non-empty assumptions/trade-offs/risks, a confidence value, and a stated remaining uncertainty — structurally enforced, not conventional. `GENERATE_RECOMMENDATION` never writes to memory itself; a separate sequencing/structuring operation performs the actual `RoadmapItem`/`Metric` write once a recommendation is acted on. `PortfolioAssessment` is structurally incapable of cross-product comparison — it gathers each named product's memory independently and reports a per-product inventory only, and every result's mandatory `scope_note` prevents that partial view from ever being presented as a complete analysis.

## Executive Interaction

Declares `AgentCapability.REASONING`/`PLANNING` only — never `MEMORY`. Roadmap and Metric records it writes are read by Stakeholder Communication for alignment narratives and status drafting, exclusively through shared memory.

## Typical Workflow

Decision Records and Discovery Findings accumulate across one or more products → a PM asks Strategy & Portfolio to sequence a roadmap or structure OKRs → the specialist retrieves grounding evidence, applies a prioritization framework, and writes a `RoadmapItem`/`Metric` (or honestly declines if evidence is thin) → the resulting roadmap becomes what Stakeholder Communication later drafts alignment narratives from, and what a future Portfolio Intelligence maturity level would compare across products, once built.

## Extension Guidance

See [Adding_Product_Management_Specialists.md](../06_DEVELOPMENT/Adding_Product_Management_Specialists.md). Portfolio Intelligence's graduation to real cross-product reasoning is this specialist's named future extension point (Product_Management_Intelligence.md) — achievable as new reasoning within this existing specialist against the memory it already has, not a new specialist or new memory category.

## Limitations

Cross-product Portfolio reasoning is dormant, not working — no cross-product comparison, dependency-conflict detection, or resource-tradeoff scoring exists yet, by design, not oversight. RICE/ICE scoring and framework selection are independently implemented in this specialist's own `scoring.py`, deliberately never importing Product Decision's equivalent module — the two are allowed to diverge slightly in judgment since they operate at different decision granularities (single decision vs. backlog-wide).
