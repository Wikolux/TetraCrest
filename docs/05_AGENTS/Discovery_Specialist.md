# Discovery Specialist

`DiscoverySpecialist` (CP-02, Milestone 3) is the first of CP-02's five specialists — see [Product_Management_Intelligence.md](../04_CAPABILITIES/Product_Management_Intelligence.md) for the pack-level guide this document sits under. It is built with zero dependency on any other CP-02 specialist's output, and is the entry point for most of a PM's evidence chain: nothing downstream (Product Decision, Delivery, Strategy) can honestly cite evidence that didn't first pass through Discovery or a delegated research question it framed.

This document contains no implementation detail and no code — it is written for anyone who needs to understand what Discovery does and guarantees without reading its source.

## Purpose

Discovery answers one question, honestly: **is this problem real, and worth solving?** It structures the earliest, most uncertain stage of product work — turning raw observations, interviews, and hypotheses into evidence a later specialist can actually build on, and refusing to manufacture certainty when the evidence doesn't support it.

## Responsibilities

Per PRD §15: problem validation, Jobs-to-be-Done framing, customer-interview and feedback synthesis, opportunity assessment (via an Opportunity Solution Tree framing), and hypothesis tracking. Discovery never prioritizes (that's Product Decision or Strategy & Portfolio's job), never drafts delivery artifacts, and never performs research itself — it frames a research question and lets the Executive delegate it to `ResearchAgent` in a later turn.

## Operations

Twelve, matching the PRD's own capability list plus the platform's standard bulk/recall operations: validate a problem statement, frame a Jobs-to-be-Done statement, synthesize a customer interview, assess an opportunity, frame a persona, track a hypothesis's status, generate an evidence-backed recommendation, run the full Discovery Session journey end to end (PRD §9.1), summarize prior findings in bulk, frame a research question for delegation, record a research finding once one comes back, and recall prior Discovery work semantically.

## Inputs

Free-text problem statements, interview notes, feedback, hypotheses, and persona details — always caller-supplied, never invented. Discovery also automatically retrieves prior relevant memory (its own past findings, and anything else semantically related) before reasoning, the same way every CP-02 specialist does.

## Outputs

A `DiscoveryFinding` (evidence and its validation status) for operations that capture evidence; a `ResearchFinding` when a delegated research result is recorded; a synthesized, evidence-cited response for every operation, whether or not it wrote a durable record. Framing-only operations (Jobs-to-be-Done, persona framing, opportunity assessment) reason over retrieved context and respond, without necessarily writing a new finding themselves — see Evidence Discipline, below, for exactly which operations write and why.

## Memory Usage

Discovery owns and writes **Discovery Finding / Hypothesis** (`product_discovery_finding`) and, when recording a delegated research result, **Research Finding** (`product_research_finding` — owned jointly with Strategy & Portfolio, whichever specialist delegated the question). It reads its own prior findings and anything else semantically relevant through `ProfessionalMemoryService`, the same organization-scoped, semantic retrieval every specialist uses — never a second memory mechanism. Every write is append-only: a hypothesis's status change is a new entry, never an edit to the original.

## Evidence Discipline

`DiscoveryFinding` cannot be constructed without a summary and a stated source — a finding that doesn't say where its evidence came from is structurally impossible to write, not merely discouraged by convention. When no relevant evidence exists, Discovery says so explicitly (low confidence, an honest "insufficient evidence" response) rather than fabricating a validated conclusion. Research is never reimplemented internally: a genuine research need becomes a framed question and a delegation-signaling event, never an attempt to perform the research itself.

## Executive Interaction

Discovery declares `AgentCapability.REASONING`/`PLANNING` — never `MEMORY`, so it can never intercept the Executive's own internal memory-retrieval tasks, and never `RESEARCH`, since research delegation remains `ResearchAgent`'s alone. Anything Discovery writes is automatically visible to the Executive's ordinary retrieval and to every other CP-02 specialist, with zero direct coupling — the only integration path any specialist uses.

## Typical Workflow

A PM describes a candidate problem → Discovery validates it against existing evidence or flags the gap → if evidence is thin, Discovery frames a research question for delegation → once research returns, Discovery records the finding → the accumulated Discovery Findings become the evidence Product Decision, Delivery, and Strategy each read through shared memory, never through a direct call to Discovery.

## Extension Guidance

See [Adding_Product_Management_Specialists.md](../06_DEVELOPMENT/Adding_Product_Management_Specialists.md) for the general path. A new Discovery-adjacent capability is very likely a new operation on this specialist (following its own evidence-and-event pattern), not a new specialist — Discovery's scope (PRD §15) has room within it that hasn't needed a sixth specialist yet.

## Limitations

Vision-assisted discovery-artifact capture (photographed whiteboards, screenshots) is named in PRD §15 as future scope, depending on a concrete Vision provider that doesn't yet exist platform-wide — not built in v1. Framing-only operations (JTBD, persona, opportunity assessment) don't always write a new Discovery Finding themselves — this is a deliberate distinction between "framing/reasoning" and "capturing evidence," not an oversight; see the specialist's own test suite for exactly which operations write and which don't.
