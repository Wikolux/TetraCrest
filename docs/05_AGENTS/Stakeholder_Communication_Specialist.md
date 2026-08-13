# Stakeholder Communication Specialist

`StakeholderCommunicationSpecialist` (CP-02, Milestone 7) is CP-02's fifth and final specialist — see [Product_Management_Intelligence.md](../04_CAPABILITIES/Product_Management_Intelligence.md) for the pack-level guide this document sits under. It translates validated product knowledge from the other four specialists into audience-appropriate communication. It drafts. It never sends.

This document contains no implementation detail and no code.

## Purpose

Stakeholder Communication answers: **given what's actually been validated, decided, and delivered, how do we tell the right audience, in the right voice, without inventing progress that hasn't happened?** It is the specialization of CP-01's Communication Intelligence into professional, product-context communication.

## Responsibilities

Per PRD §18: stakeholder mapping (a RACI-style view of who is responsible/accountable/consulted/informed for a decision or delivery effort), status updates and executive summaries (audience-appropriate, never invented progress), alignment narratives (the "why" behind a roadmap or prioritization call), and voice/tone drawn from the user's own communication style via CP-01 Identity Intelligence — never a separate, CP-02-private notion of voice. The hard constraint inherited from CP-01: **nothing is sent autonomously, ever.**

## Operations

Five: map a stakeholder (with an optional RACI role), draft a communication (one unified operation, parameterized by audience and purpose — covering all twelve of PRD's named drafting responsibilities, from executive summaries through portfolio communication, never twelve near-duplicate operations), explain a decision, summarize communications in bulk, and recall prior communication work.

## Inputs

A stakeholder's name, role/interest, and optional RACI role; an audience and purpose for a draft; a decision to explain; and — read automatically — Roadmap State, Delivery Artifacts, Decision Records, and Discovery Findings relevant to what's being communicated.

## Outputs

A `Stakeholder` record for stakeholder mapping; a `DeliveryArtifact` tagged `DeliveryArtifactType.COMMUNICATION_DRAFT` for every drafted communication (reusing the Delivery Artifact category, not a new memory type — ARR §3's own literal instruction); a `DecisionExplanation` for decision-explaining requests. Every successful draft's own response states explicitly that it was not sent.

## Memory Usage

Owns and writes **Stakeholder Record** (`product_stakeholder`) and drafted communication as a `product_delivery_artifact`-shaped record (Delivery's own category, extended with one new, purely additive `DeliveryArtifactType.COMMUNICATION_DRAFT` member rather than a new namespace). Reads Roadmap State, Delivery Artifacts, Decision Records, and Discovery Findings through `ProfessionalMemoryService.recall()` — never a direct import of any of the other four specialists' code. Never writes a `DecisionRecord`, `RoadmapItem`, or `Metric`. Every write is append-only.

## Evidence Discipline

`CommunicationDraft`/`DecisionExplanation` cannot be constructed without referenced memory IDs or an explicit evidence gap, non-empty assumptions, and a valid confidence value — structurally enforced. When no evidence is retrieved, drafting or explaining declines to write an artifact and honestly recommends further Discovery or Decision Support instead. When a named stakeholder has no Stakeholder Record on file, an honest placeholder assumption is recorded and actually reaches the persisted draft — never silently assumed and left untracked.

## Executive Interaction

Declares `AgentCapability.REASONING`/`PLANNING`, **plus `AgentCapability.COMMUNICATION`** — the one capability difference among CP-02's five specialists, and never `MEMORY`. Nothing it produces is ever sent: verified structurally (no method or module-level function with a sending name exists anywhere on the class), not merely by policy.

## Typical Workflow

Roadmap items are sequenced, decisions are recorded, delivery artifacts exist → a PM asks Stakeholder Communication to draft an executive summary or explain a decision to a specific audience → the specialist retrieves the grounding evidence and drafts, citing what it found and flagging any placeholder assumption about the audience → the user reviews and sends it themselves, through whatever channel they choose — this specialist never touches that channel.

## Extension Guidance

See [Adding_Product_Management_Specialists.md](../06_DEVELOPMENT/Adding_Product_Management_Specialists.md). A new audience or purpose for drafting is a parameter value on the existing `DRAFT_COMMUNICATION` operation, never a new operation — this specialist's own "one pattern, not one per channel" principle (Architecture §11) should be the default assumption for any new communication-shaped request.

## Limitations

Nothing is ever sent, in any channel, by design — this is permanent, not a v1 gap. Voice/tone is read from CP-01 Identity Intelligence; if a user hasn't set communication preferences there, drafts fall back to a neutral default rather than guessing a style. RACI role, when set on a `Stakeholder`, is scoped to that mention — a person's role can differ across different stakeholder-mapping calls for different efforts, since Stakeholder Records are append-only per mention, not a single mutable profile.
