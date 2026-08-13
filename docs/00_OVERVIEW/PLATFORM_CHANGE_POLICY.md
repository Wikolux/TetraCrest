# Tetra OS — Platform Change Policy

| | |
|---|---|
| **Scope** | How the platform itself (not a Capability Pack, not an Application) may change after Version 1 |
| **Authority** | A process document, not a fifth governance authority — it extends, and never outranks, [MASTER_BLUEPRINT.md](../MASTER_BLUEPRINT.md), [PRODUCT_PHILOSOPHY_FREEZE_v1.md](../PRODUCT_PHILOSOPHY_FREEZE_v1.md), [ARCHITECTURE_FREEZE_v1.md](../ARCHITECTURE_FREEZE_v1.md), and [VERSION_1_PLATFORM_BASELINE.md](VERSION_1_PLATFORM_BASELINE.md). It sits alongside [VERSION_1_DEVELOPMENT_GUIDE.md](../VERSION_1_DEVELOPMENT_GUIDE.md) as a process document, not above it — that guide governs how a *Capability Pack* is built; this one governs how the *platform itself* may change. Neither replaces the other, and neither governs the other's subject. |
| **Does not govern** | Capability Packs (see `VERSION_1_DEVELOPMENT_GUIDE.md`) or Applications (see `VERSION_1_PLATFORM_BASELINE.md`'s Application Layer Definition) — both build *on* the platform and are, by definition, out of this document's scope. |
| **Operationalizes** | `ARCHITECTURE_FREEZE_v1.md`'s existing Compatibility Policy (semantic versioning, MAJOR/MINOR/PATCH) and Future Development Rules (the explicit "may not redesign" list). This document does not redefine what counts as breaking — that answer already exists. It defines the *process* a platform-level change goes through before it can happen at all, which did not exist as a written process before this document. |
| **Status** | Established. Amended only through its own lifecycle (§"Platform Governance Lifecycle," below) applied to itself — a change to this policy is itself a platform-level governance decision. |

---

## Principles

- **Stability is preferred over novelty.** The platform's value is that it can be built on with confidence — a platform that changes often is a platform nothing can safely depend on.
- **Extension is preferred over modification.** Every Capability Pack built so far (CP-01, CP-02) shipped to full release without modifying a single frozen interface. This is the default outcome to expect, not a fortunate accident.
- **Capability Packs extend the platform.** They register into existing extension points; they do not, and structurally cannot, redefine what the platform is.
- **Applications consume Capability Packs.** An Application composes packs that already exist into a real-world workflow; it does not require the platform, or any pack, to change on its behalf (`VERSION_1_PLATFORM_BASELINE.md`, "Relationship to Applications," below).
- **Platform evolution is the exception, not the default.** A platform-level change is not a normal unit of work, the way a new pack or a new Application is. It is a deliberate, evidence-gated departure from the default of extension.

## Platform Change Philosophy

The platform is considered stable, per `ARCHITECTURE_FREEZE_v1.md`'s own declaration at M20.7, now further evidenced by two full Capability Pack releases without a single frozen-interface modification (`VERSION_1_PLATFORM_BASELINE.md`, "Platform Freeze"). Future work — whatever problem it is trying to solve — is expected to first attempt, in this order:

1. **Reuse existing architecture.** Is there already a framework, adapter, or registry that does this?
2. **Extend existing contracts.** Can a new optional parameter, a new enum member, a new subclass, or a new registered entry solve this without touching an existing signature (`ARCHITECTURE_FREEZE_v1.md`'s own "What's Considered Safe")?
3. **Compose existing capabilities.** Can a Capability Pack or an Application combine what already exists — including across pack boundaries, through shared memory and Executive dispatch, never direct import — to solve this?

**Only after all three have been genuinely attempted and found insufficient — not merely inconvenient — should platform modification be considered.** The burden of proof sits with the change, not with the platform's stability.

## Change Categories

Every proposed change to the codebase falls into exactly one category. The category determines the process, not the size of the diff.

### Category A — Maintenance

**Examples**: bug fixes, documentation corrections, test improvements, performance improvements with no observable behavior change.

**Maps to**: `ARCHITECTURE_FREEZE_v1.md`'s existing **PATCH** definition, verbatim — this category is not new; it is named here so it has an explicit home in this policy's own decision tree.

**Process**: normal code review. No governance approval beyond that — the same bar every fix in this platform's history has already been held to.

### Category B — Capability Extension

**Examples**: a new Capability Pack, a new Application, a new Connector.

**Constraint**: must not modify platform architecture. A pack or Application that finds itself needing to is not a Category B change at all — it has surfaced a Category C or D need underneath it, and should be redirected there, not built as a workaround.

**Process**: governed entirely by `VERSION_1_DEVELOPMENT_GUIDE.md` (Capability Packs) or `VERSION_1_PLATFORM_BASELINE.md`'s Application Layer Definition (Applications) — not by this document. As `ARCHITECTURE_FREEZE_v1.md` already states, a Capability Pack's own version is independent of the platform's version; this remains true without exception.

### Category C — Platform Enhancement

**Examples**: adding a reusable framework (the way Vision was added, capability-first and vendor-last), introducing a new platform-wide service, adding a new cross-cutting abstraction available to every future pack.

**Maps to**: `ARCHITECTURE_FREEZE_v1.md`'s existing **MINOR** definition — "a new capability framework is added following `Adding_Framework.md`" is explicitly named there as MINOR, not MAJOR, and this policy does not change that classification. What it adds is process: a Category C change is additive to every existing frozen interface (nothing removed, nothing redefined) but introduces enough new platform surface that Capability Pack-level review is insufficient.

**Process**: **requires formal review** — a written Platform Change Proposal (§ below), evaluated against the Approval/Rejection Criteria (§ below), reviewed with independent rigor comparable to a Capability Pack's own Architecture Readiness Review. No ADR is required by default (MINOR changes don't require one per `ARCHITECTURE_FREEZE_v1.md`), but the reviewing party may require one if the proposal's own risk profile warrants it.

### Category D — Architectural Change

**Examples**: changing Runtime contracts, Executive redesign, Memory redesign, Registry redesign, Event architecture changes — precisely the list `ARCHITECTURE_FREEZE_v1.md`'s own "Future Development Rules" names as things "no future milestone or Capability Pack may [do]... unless a future MAJOR version explicitly replaces them."

**Maps to**: `ARCHITECTURE_FREEZE_v1.md`'s existing **MAJOR** definition — this policy does not redefine what counts as breaking. It is the authoritative source; this document only adds the proposal process leading up to it.

**Process**: highest approval level. Requires a full Platform Change Proposal, an ADR justifying the change (`ARCHITECTURE_FREEZE_v1.md` already mandates this for MAJOR changes), a migration note, and `ARCHITECTURE_FREEZE_v1.md` itself re-issued as a new frozen version. Must satisfy every Approval Criterion below with no exceptions — Category D is where "extension, composition, and Capability Pack implementation have been exhausted" must be demonstrated, not asserted.

## Platform Change Decision Tree

```
Problem discovered
        ↓
Can existing platform architecture solve it, as-is?
        ↓ YES → Use the existing mechanism. STOP. (Not a change at all.)
        ↓ NO
Is this a bug, doc error, or non-behavioral improvement?
        ↓ YES → Category A (Maintenance). Normal review. STOP.
        ↓ NO
Can a Capability Pack or Application extend/compose existing
architecture to solve it, without touching a frozen interface?
        ↓ YES → Category B (Capability Extension). Implement inside
        ↓        the pack or Application, per its own lifecycle. STOP.
        ↓ NO
Does solving it require new platform-wide surface (a new framework,
service, or cross-cutting abstraction) — additive only, nothing
frozen removed or redefined?
        ↓ YES → Category C (Platform Enhancement). Platform Change
        ↓        Proposal + formal review required. STOP once approved.
        ↓ NO
Does solving it require redesigning a frozen interface, contract,
or mechanism named in ARCHITECTURE_FREEZE_v1.md?
        ↓ YES → Category D (Architectural Change). Full Platform
                 Change Proposal + ADR + migration note + re-issued
                 Architecture Freeze required. Highest bar. STOP
                 once approved — implementation does not begin on
                 the strength of the proposal alone.
```

A "STOP" at any earlier branch is the expected, common outcome. Reaching Category D should be rare — evidenced by the fact that it has not happened once across two full Capability Pack releases.

## Platform Change Proposal Requirements

Every Category C or D proposal must include all of the following. A proposal missing any section does not proceed to review.

- **Problem statement** — what, precisely, cannot be done today.
- **Evidence** — a real, observed instance of the problem, not a hypothetical one. Per Capability_Strategy.md's own established discipline: duplication and gaps are found in hindsight, from real attempts, not predicted in advance.
- **Affected components** — every frozen package, interface, or extension point the change would touch.
- **Alternatives considered** — specifically, what was tried at the Reuse / Extend / Compose stages (§"Platform Change Philosophy") before concluding none was sufficient.
- **Why extension is insufficient** — not "less convenient" — a concrete statement of what extension cannot achieve.
- **Backward compatibility assessment** — what existing Capability Packs or Applications would be affected, and how.
- **Migration strategy** — how existing consumers move to the new shape, if anything must move at all.
- **Risks** — technical, and to platform stability generally.
- **Expected benefits** — concretely, not aspirationally.
- **Implementation scope** — what would actually need to be built, and where.

## Approval Criteria

A proposal may be approved only if it demonstrates:

- **Real evidence** — an actual, observed problem, not a projected one.
- **A repeatable problem** — not a one-off.
- **Impact across multiple Capability Packs or Applications** — a single pack's own need is addressed in §"Relationship to Capability Packs," below, not here.
- **That the problem cannot be solved through extension** — genuinely, not merely more slowly or less elegantly through extension.
- **Alignment with platform philosophy** — `MASTER_BLUEPRINT.md` and `PRODUCT_PHILOSOPHY_FREEZE_v1.md`, never contradicted for engineering convenience.
- **Backward compatibility preserved wherever possible** — and explicitly justified wherever it genuinely cannot be.

## Rejection Criteria

A proposal is rejected if it is found to be any of the following — these are not exhaustive, but each has independent precedent in this platform's own stated design values:

- **Convenience only** — solvable by extension, just less conveniently.
- **A pack-specific workaround** — the proposer's own pack needs it; nothing else does (see §"Relationship to Capability Packs").
- **Duplicative** — the platform, or the pack being built on, already provides this (`Vision.md`'s "Compose, never duplicate").
- **A violation of the Architecture Freeze** with no MAJOR-version justification attached.
- **Introduces unnecessary coupling** — between packs, or between the platform and a specific vendor/pack's internal shape.
- **Solves a hypothetical future problem** — `Vision.md`'s own "No speculative abstraction": shared infrastructure is extracted after a real, observed duplication, never in anticipation of one.

## Versioning Policy

This policy does not redefine `ARCHITECTURE_FREEZE_v1.md`'s existing semantic versioning — it clarifies which category of work belongs to which version track:

| Work | Version | Governing definition |
|---|---|---|
| Category A (Maintenance) | PATCH | `ARCHITECTURE_FREEZE_v1.md`'s existing PATCH definition |
| Category B (Capability Extension) | Independent of the platform version entirely | A pack or Application ships its own version; "a new Capability Pack ships" is itself listed as MINOR only in the sense that the platform's own MINOR counter may move, never because the pack forced a platform change |
| Category C (Platform Enhancement) | MINOR | `ARCHITECTURE_FREEZE_v1.md`'s existing MINOR definition |
| Category D (Architectural Change) | MAJOR — i.e., **Version 2** | `ARCHITECTURE_FREEZE_v1.md`'s existing MAJOR definition, and `VERSION_1.0_MILESTONE_ZERO.md` §14's own "Definition of Success for Version 2" |

**Version 2 begins only when a genuine architectural limitation cannot reasonably be addressed through extension** — `VERSION_1.0_MILESTONE_ZERO.md` §14's own words, restated here because it is the exact bar every Category D proposal must clear, not a new bar invented for this document. Version numbers are never created for feature accumulation alone — CP-01 and CP-02 together shipped 8 specialists and 16 memory categories without moving the platform's own version past what MINOR already covers (new packs, new registered entries).

## Documentation Requirements

Every **approved** platform change updates only the living documentation genuinely affected by it — never a frozen historical document, and never a document the change didn't actually touch:

- **`ARCHITECTURE_FREEZE_v1.md`** — required for any Category D change (a MAJOR change re-issues this document, per its own Future Development Rules); not touched for Category A/B, and touched for Category C only if the new framework/service is itself added to the Stable Packages table.
- **ADRs** — required for Category D (per `ARCHITECTURE_FREEZE_v1.md`'s own MAJOR definition); optional, at the reviewer's discretion, for Category C.
- **`Capability_Strategy.md`** — updated only if the change affects the Reuse Contract or Pack Independence rules every pack depends on.
- **`VERSION_1_PLATFORM_BASELINE.md`** — updated only when a Category C or D change genuinely changes what a future pack or Application can assume is already built (its own stated update trigger).
- **`Roadmap.md`** — every approved Category C or D change gets a chronological entry, mirroring how every Capability Pack milestone already does.
- **`CAPABILITY_READINESS.md`** — updated only if the change affects a specific capability's own CRL or blocking items.

**Never updated by a platform change, under any category**: `MASTER_BLUEPRINT.md`, `PRODUCT_PHILOSOPHY_FREEZE_v1.md`, and `VERSION_1.0_MILESTONE_ZERO.md` — the first two because a platform change does not alter why the platform exists or what it permanently believes; the third because it is, by its own explicit text, a one-time historical record, never revised as the platform grows.

## Change Traceability

Every **approved** platform change (Category C or D) records:

- **Date** approved.
- **Reason** — the evidence and problem statement from its own proposal, not restated from memory.
- **Approving authority** — whoever conducted the review (mirroring how a Capability Pack's Architecture Readiness Review names its own reviewer role, without requiring a specific named individual to be hardcoded into permanent governance).
- **Affected documents** — the specific list from §"Documentation Requirements" that actually got updated.
- **Affected components** — the specific frozen packages/interfaces touched (Category D) or added (Category C).
- **Related ADR**, if one exists.

This is the same traceability discipline ADR-0006 already established for memory-type decisions, applied to platform-level changes generally rather than to one specific decision type.

## Compatibility Policy

This section states expectations; it does not redefine `ARCHITECTURE_FREEZE_v1.md`'s own Compatibility Policy, which remains the authoritative source for what MAJOR/MINOR/PATCH mean.

- **Backward compatibility** is the default expectation for every change. A Category C change adds; it does not alter what already exists in an incompatible way — this is what keeps it MINOR rather than MAJOR.
- **Migration guidance** is mandatory for any Category D change, as part of its own proposal (§"Platform Change Proposal Requirements") and, if approved, published alongside the re-issued Architecture Freeze.
- **Deprecation** — the platform has not yet deprecated a frozen interface, and this policy does not introduce a deprecation mechanism it doesn't already have (`GenericEvent`/`GenericMiddleware`/etc. have no "deprecated" state today). Should this become necessary, defining that mechanism is itself a Category C proposal, not something this policy resolves in advance of a real need — consistent with "no speculative abstraction."
- **Transition periods** are set case-by-case in an approved Category D change's own migration note; this policy does not pre-define a fixed length, since none has ever been needed yet.
- **Breaking changes require exceptional justification** — every Approval Criterion in this document must hold, with no exceptions, before a breaking (Category D / MAJOR) change proceeds.

## Relationship to Capability Packs

Capability Packs do not redefine the platform — they are built entirely on top of it, using only its existing extension points, per the Reuse Contract already established in `Capability_Strategy.md`. **Capability Packs demonstrate whether the platform is sufficient.** CP-01 and CP-02, taken together, are now direct, cited evidence that it is: two structurally different packs, eight specialists, sixteen memory categories, zero platform modifications.

**Repeated evidence from multiple Capability Packs may justify a future platform proposal.** If a third, fourth, and fifth pack each independently found the same genuine limitation — not merely each wanted the same convenience — that repetition is exactly the kind of real, repeatable evidence §"Approval Criteria" requires.

**One Capability Pack alone normally does not.** A single pack's own friction is, by default, a signal to look harder at extension (§"Platform Change Philosophy"), not a mandate to change the platform on that pack's behalf. This is not a bureaucratic obstacle — it is what "Capability Packs demonstrate whether the platform is sufficient" means in practice: one data point demonstrates very little; a pattern across independent packs demonstrates something real.

## Relationship to Applications

Applications are expected to innovate — an Application's whole purpose is to combine existing Capability Packs into a real-world workflow no single pack was built to anticipate (`VERSION_1_PLATFORM_BASELINE.md`'s own Application Layer Definition). **Application-specific requirements should not automatically become platform requirements.** An Application that needs something a pack doesn't yet provide is evidence for that pack's own next operation (Category B, governed by that pack's own lifecycle) — not, by itself, evidence for a platform change.

**Applications may compose multiple Capability Packs without changing the platform** — this is the entire point of the Application layer existing as its own tier, distinct from both the platform and any single pack (`VERSION_1_PLATFORM_BASELINE.md`).

## Platform Governance Lifecycle

For any Category C or D proposal:

```
Proposal
   ↓
Review (against Approval/Rejection Criteria, above)
   ↓
Evidence Validation (is the problem real, repeatable, and cross-pack where claimed?)
   ↓
Architecture Assessment (does it genuinely require this category, or does it
                          actually resolve at Category B on closer inspection?)
   ↓
Approval / Rejection
   ↓
Implementation (only after approval — never in parallel with review)
   ↓
Documentation (§"Documentation Requirements" — only what's genuinely affected)
   ↓
Verification (full platform regression suite, zero regressions, mirroring
              the standard every Capability Pack has already been held to)
   ↓
Platform Baseline Update (only when the change genuinely affects what a
                           future pack or Application can assume — not automatic)
```

Rejection may occur at Review, Evidence Validation, or Architecture Assessment — a proposal does not need to reach Approval/Rejection formally to be turned back if it fails an earlier stage on its face.

---

## Final Declaration

The Tetra OS Platform is intended to evolve deliberately rather than continuously.

Platform stability is a strategic asset — not the absence of ambition, but the precondition for every Capability Pack and Application that depends on the platform not moving underneath it.

Every proposed change must demonstrate that extension, composition, and Capability Pack implementation have been exhausted before platform modification is considered.

The Platform Change Policy exists to preserve the long-term integrity, consistency, maintainability, and scalability of Tetra OS.
