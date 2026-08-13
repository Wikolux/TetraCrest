# Platform Innovation Backlog

| | |
|---|---|
| **Status** | Living document — vision capture only, updated whenever a new idea surfaces |
| **Authority** | Not a governance document and not a commitment — an idea recorded here has no roadmap standing until it earns a PRD (Phase 1 of the [Version 1 Development Guide](VERSION_1_DEVELOPMENT_GUIDE.md)) and a place in [Capability_Strategy.md](08_CAPABILITY_PACKS/Capability_Strategy.md) |
| **Complements** | [CAPABILITY_READINESS.md](CAPABILITY_READINESS.md) — an idea here is, by definition, CRL-0 and not yet listed there; the moment it gets a PRD, it graduates out of this document and into that dashboard |

## Purpose

Good ideas surface constantly, mid-implementation, when they are least safe to act on. This document exists to catch them without acting on them — a place to write an idea down completely enough that it isn't lost, explicitly outside the current implementation's scope, so that CP-02 (or whatever Capability Pack is active) is never tempted to quietly absorb scope creep just because an idea was fresh when it was thought of. Nothing here is scheduled. Nothing here is designed. An idea graduates out of this backlog only by going through Phase 1 (PRD) of the Version 1 Development Guide, the same door every real capability walks through.

Each entry uses the same nine fields, so any idea can be scanned and compared quickly:

- **Idea** — one line, what it is
- **Problem Solved** — what's broken or missing without it
- **Why It Matters** — the case for it, briefly
- **Priority** — a rough signal only (High / Medium / Low, or Unranked), never a schedule commitment
- **Dependencies** — what would need to exist first
- **Potential Capability Pack** — best-guess home, or "New Pack" / "Unclear" if none fits
- **Suggested Version** — a loose guess (v1.x, v2, "post-v2"), never binding
- **Status** — Idea / Under Consideration / Superseded / Rejected / Future Vision (a deliberately durable, long-horizon direction the platform has explicitly committed to remembering — not a schedule, not a milestone, but a stronger form of "keep this" than an ordinary Idea; still leaves this backlog only through Phase 1, exactly like any other entry)
- **Notes** — anything else worth remembering

---

## Meeting Intelligence Cluster

### Meeting Intelligence (umbrella capability)

| Field | Value |
|---|---|
| **Idea** | A capability that understands meetings as a first-class unit of professional life — not just their content, but their purpose, participants, and outcomes over time. |
| **Problem Solved** | Meetings currently produce no durable, structured memory anywhere on the platform; everything discussed in them is lost the moment the meeting ends unless a user manually writes it down elsewhere. |
| **Why It Matters** | Meetings are one of the highest-density sources of professional information a PM, executive, or knowledge worker generates — exactly the kind of raw material CP-01 and CP-02's memory-driven intelligence already thrives on. |
| **Priority** | Medium |
| **Dependencies** | Conversation Framework (a concrete provider), Vision Framework (a concrete provider, for shared-screen/slide capture), Memory Framework |
| **Potential Capability Pack** | New Pack — likely parent to the three items below, which may be its milestones rather than separate packs |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | Named explicitly by the product owner as a priority cluster; the three items below were named alongside it and are treated as its likely first capabilities rather than independent packs, pending a real PRD. |

### Meeting Note Taker

| Field | Value |
|---|---|
| **Idea** | Automatic, structured capture of what was said and decided in a meeting, without a human manually taking notes. |
| **Problem Solved** | Manual note-taking during a meeting competes with actually participating in it; notes taken this way are inconsistent and often incomplete. |
| **Why It Matters** | The most direct, lowest-friction way to get meeting content into the platform's memory at all. |
| **Priority** | Medium |
| **Dependencies** | Meeting Intelligence (umbrella), a concrete Conversation/transcription provider |
| **Potential Capability Pack** | Meeting Intelligence |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | Likely the first concrete milestone of Meeting Intelligence, if that pack is ever chartered. |

### Meeting Action Tracking

| Field | Value |
|---|---|
| **Idea** | Extract action items and commitments from meetings and track them to completion, across meetings. |
| **Problem Solved** | Action items agreed upon verbally in a meeting routinely get lost, duplicated, or forgotten by the next one. |
| **Why It Matters** | Turns Meeting Note Taker's raw capture into something that changes what actually gets done — the difference between a transcript and an outcome. |
| **Priority** | Medium |
| **Dependencies** | Meeting Note Taker, a durable task/commitment representation (none currently exists platform-wide) |
| **Potential Capability Pack** | Meeting Intelligence |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | Overlaps conceptually with CP-02's Delivery Specialist (now shipped and released — see [Delivery_Specialist.md](05_AGENTS/Delivery_Specialist.md)) — worth checking for shared representation with its `DeliveryArtifact`/`FeatureInitiative` model before inventing a separate "action item" concept, should this idea ever graduate past Phase 1. |

### Interview Copilot

| Field | Value |
|---|---|
| **Idea** | Real-time assistance during a live interview — for the interviewer (suggested follow-ups, coverage tracking) or the candidate (practice, structure). |
| **Problem Solved** | Interviews are high-stakes, single-shot conversations with no assistance available in the moment. |
| **Why It Matters** | A concrete, high-value application of live meeting assistance with a clear, well-understood use case. |
| **Priority** | Low |
| **Dependencies** | Live Meeting Assistant (below) — this is best understood as a specialization of that, not a separate mechanism |
| **Potential Capability Pack** | Meeting Intelligence |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | Raises real-time ethical/disclosure questions (is the other party aware assistance is active?) that a future PRD must address before any design work begins. |

### Live Meeting Assistant

| Field | Value |
|---|---|
| **Idea** | Real-time, in-the-moment assistance during any live meeting — surfacing relevant memory, flagging open questions, tracking coverage against an agenda. |
| **Problem Solved** | All of the platform's intelligence today is retrospective (memory is written and recalled after the fact); nothing currently assists a user while a conversation is actually happening. |
| **Why It Matters** | A meaningfully different interaction mode from everything the platform currently does — proactive-in-the-moment rather than proactive-between-sessions (the mode CP-01.3's Insight Engine already established). |
| **Priority** | Low |
| **Dependencies** | Meeting Note Taker, real-time/streaming support (the Runtime and Conversation Framework are currently request/response, not streaming), Memory Framework |
| **Potential Capability Pack** | Meeting Intelligence |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | The most architecturally ambitious item in this cluster — likely requires new platform-level real-time infrastructure, not just a new pack, so it belongs squarely in "vision capture only" for now. |

## Language Cluster

### Universal Language Layer

| Field | Value |
|---|---|
| **Idea** | A platform-wide capability so a user's own language is never a barrier to using the system, in either direction (input or output). |
| **Problem Solved** | Today, the platform's effective language is implicitly whatever language its providers and prompts are written in — a real barrier already named as a philosophical concern. |
| **Why It Matters** | Directly extends an already-adopted belief — the Universal Language Philosophy in [PRODUCT_PHILOSOPHY_FREEZE_v1.md](PRODUCT_PHILOSOPHY_FREEZE_v1.md) §7 and [MASTER_BLUEPRINT.md](MASTER_BLUEPRINT.md) §17 — from stated belief into an actual, buildable capability. |
| **Priority** | Medium |
| **Dependencies** | Conversation Framework (concrete provider with strong multilingual support) |
| **Potential Capability Pack** | Language Intelligence (already named in Master Blueprint §15, currently CRL-0) |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | This is the most directly philosophy-grounded idea in this backlog — a future PRD should cite Product Philosophy Freeze §7 explicitly rather than re-deriving the justification. |

### Language Practice Companion

| Field | Value |
|---|---|
| **Idea** | A dedicated companion experience for practicing a new language through conversation, drawing on the platform's existing companion/memory strengths. |
| **Problem Solved** | Language learning tools today are largely drill-based; they don't remember a learner's specific struggles, goals, or progress the way this platform's Memory Framework already can. |
| **Why It Matters** | A natural, high-fit application of CP-01's existing personal-memory strengths to a concrete, well-understood market need. |
| **Priority** | Low |
| **Dependencies** | Universal Language Layer, Personal Intelligence (CP-01) |
| **Potential Capability Pack** | Language Intelligence |
| **Suggested Version** | Post-v2 |
| **Status** | Idea |
| **Notes** | None |

### Voice Conversation Mode

| Field | Value |
|---|---|
| **Idea** | Spoken, voice-native interaction with the platform, rather than text-only. |
| **Problem Solved** | Text-only interaction excludes users for whom typing is slower, harder, or less natural than speaking — including many of the low-literacy and accessibility scenarios named elsewhere in this backlog. |
| **Why It Matters** | A cross-cutting enabler, not a single-pack feature — voice would benefit nearly every existing and future capability, from Meeting Intelligence to Personal Intelligence to Market Trader Experience. |
| **Priority** | Medium |
| **Dependencies** | Conversation Framework (a concrete voice-capable provider), real-time/streaming infrastructure |
| **Potential Capability Pack** | Unclear — likely platform infrastructure rather than any single Capability Pack, given how many packs would consume it |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | Shares real-time infrastructure needs with Live Meeting Assistant; worth designing together if both are ever chartered, rather than building the same real-time layer twice. |

## Access & Experience Cluster

### Offline Intelligence

| Field | Value |
|---|---|
| **Idea** | Meaningful platform functionality that continues to work without a live network connection. |
| **Problem Solved** | The platform today assumes continuous connectivity — a real barrier in low-connectivity regions and for the Market Trader and Farmer experiences named below. |
| **Why It Matters** | A precondition for several other ideas in this backlog (Market Trader Experience, Farmer Experience) actually being usable by the people they're meant for. |
| **Priority** | Medium |
| **Dependencies** | None yet identified — this is itself foundational; would need its own architectural investigation before any dependent idea could be designed responsibly |
| **Potential Capability Pack** | Unclear — likely platform infrastructure |
| **Suggested Version** | Post-v2 |
| **Status** | Idea |
| **Notes** | Should be evaluated early relative to Market Trader Experience and Farmer Experience, since both may be infeasible without it. |

### Market Trader Experience

| Field | Value |
|---|---|
| **Idea** | An experience tailored to informal-market traders — simple, fast, resilient to intermittent connectivity, built around their actual daily workflow rather than a generic business tool cut down. |
| **Problem Solved** | Existing business/productivity tooling (including this platform's own current design) assumes a desk-based, always-connected, literate professional user — a poor fit for this audience. |
| **Why It Matters** | A concrete expression of the platform's stated inclusivity ambitions reaching a genuinely underserved audience, not just a new market segment. |
| **Priority** | Low |
| **Dependencies** | Offline Intelligence, Low-literacy Experience, Voice Conversation Mode |
| **Potential Capability Pack** | New Pack |
| **Suggested Version** | Post-v2 |
| **Status** | Idea |
| **Notes** | Has the deepest dependency chain in this backlog — genuinely not buildable until several other ideas here mature first. |

### Farmer Experience

| Field | Value |
|---|---|
| **Idea** | An experience tailored to smallholder farmers — seasonal planning, market pricing awareness, resilient to intermittent connectivity. |
| **Problem Solved** | Same class of problem as Market Trader Experience: existing tooling doesn't fit this audience's context or constraints. |
| **Why It Matters** | Same rationale as Market Trader Experience — a concrete expression of inclusivity reaching an underserved audience. |
| **Priority** | Low |
| **Dependencies** | Offline Intelligence, Low-literacy Experience, Voice Conversation Mode, Community Knowledge |
| **Potential Capability Pack** | New Pack — possibly the same pack as Market Trader Experience, or a sibling under a shared "Agricultural/Informal Economy" umbrella; not yet named anywhere in Master Blueprint §15 and should not be treated as a committed roadmap item |
| **Suggested Version** | Post-v2 |
| **Status** | Idea |
| **Notes** | Not currently a named future pack in [MASTER_BLUEPRINT.md](MASTER_BLUEPRINT.md) §15 — captured here at idea stage only, deliberately not added to [CAPABILITY_READINESS.md](CAPABILITY_READINESS.md) as a roadmap row until it has a real PRD. |

### Community Knowledge

| Field | Value |
|---|---|
| **Idea** | A way for knowledge to be shared and built collectively within a community of users, rather than remaining siloed per individual. |
| **Problem Solved** | Every memory on the platform today belongs to one organization/user; there's no mechanism for community-level shared understanding (relevant to Farmer Experience and Human Teaching Mode alike). |
| **Why It Matters** | A genuinely different memory-sharing model from anything currently frozen into the architecture — worth thinking through carefully rather than bolting on. |
| **Priority** | Low |
| **Dependencies** | Memory Framework (would likely need new sharing/visibility semantics — a significant design question, not a small extension) |
| **Potential Capability Pack** | Unclear |
| **Suggested Version** | Post-v2 |
| **Status** | Idea |
| **Notes** | Any real design here would need to grapple directly with the platform's current per-organization memory isolation — flagged as a nontrivial architectural question for whenever this is seriously considered, not something to design in passing. |

### Human Teaching Mode

| Field | Value |
|---|---|
| **Idea** | A mode where the platform explicitly teaches a human a skill or concept, rather than doing the work on their behalf. |
| **Problem Solved** | Every current capability is built around the platform acting for the user (remembering, deciding, drafting); nothing is built around the platform explicitly building the user's own capability. |
| **Why It Matters** | A distinct interaction philosophy worth naming and preserving as an option, particularly relevant to Personal Coaching and Education Intelligence. |
| **Priority** | Low |
| **Dependencies** | Personal Intelligence (CP-01), Education Intelligence (if chartered) |
| **Potential Capability Pack** | Education Intelligence (already named in Master Blueprint §15, currently CRL-0) |
| **Suggested Version** | Post-v2 |
| **Status** | Idea |
| **Notes** | None |

### Personal Coaching

| Field | Value |
|---|---|
| **Idea** | Proactive, ongoing coaching toward a user's personal or professional goals, building on top of what CP-01 and the Insight Engine already know about them. |
| **Problem Solved** | CP-01.3's Insight Engine already detects patterns, contradictions, and misalignments — but stops at surfacing them, rather than actively coaching the user through addressing them. |
| **Why It Matters** | The most natural next step beyond the Insight Engine's current proactive-recommendation behavior — moving from CRL-3 toward CRL-4 on the *Companion* Readiness Level scale (see [CAPABILITY_READINESS.md](CAPABILITY_READINESS.md)'s disambiguation of that scale from this dashboard's own Capability Readiness Level). |
| **Priority** | Medium |
| **Dependencies** | Personal Intelligence (CP-01), Insight Engine (CP-01.3) |
| **Potential Capability Pack** | Personal Intelligence (CP-01) extension, or a new pack if scope grows large enough to warrant one |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | Worth revisiting once CP-01's deferred Decision/Learning intelligence areas (Architecture §3) are scoped, since coaching likely depends on both. |

## Memory & Context Cluster

### Life Event Timeline

| Field | Value |
|---|---|
| **Idea** | A chronological view of significant life events, assembled from memory across every Capability Pack a user touches. |
| **Problem Solved** | Memory today is retrieved by relevance to a query, never browsed chronologically as a coherent life narrative. |
| **Why It Matters** | A different, complementary way of consuming the same memory corpus the platform already stores — narrative rather than retrieval-driven. |
| **Priority** | Low |
| **Dependencies** | Memory Framework, Memory Timeline (below) — likely the same underlying capability, applied specifically to life events |
| **Potential Capability Pack** | Personal Intelligence (CP-01) extension |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | Consider designing alongside Memory Timeline rather than as a separate mechanism, since both are chronological views over the same store. |

### Cross-device Context

| Field | Value |
|---|---|
| **Idea** | Continuity of context as a user moves between devices, so a conversation or task doesn't reset when the device changes. |
| **Problem Solved** | Nothing in the current architecture is device-aware; context handoff between devices has never been designed. |
| **Why It Matters** | Table-stakes for a companion experience meant to feel continuous rather than session-bound. |
| **Priority** | Medium |
| **Dependencies** | Runtime, Memory Framework — would need investigation into what, if anything, is currently device-specific |
| **Potential Capability Pack** | Unclear — likely platform infrastructure |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | None |

### Memory Timeline

| Field | Value |
|---|---|
| **Idea** | A chronological, browsable view over a user's or organization's memory corpus, independent of any specific query. |
| **Problem Solved** | Same gap as Life Event Timeline, generalized: there is currently no way to browse memory except by asking it a question. |
| **Why It Matters** | Would benefit every Capability Pack simultaneously, since it operates on the shared Memory Framework rather than any one pack's domain objects. |
| **Priority** | Low |
| **Dependencies** | Memory Framework, `AIMemoryService.list_memories()` (already exists and already proven as CP-02's `list_by_memory_type()` pagination base) |
| **Potential Capability Pack** | Unclear — likely platform infrastructure |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | Of everything in this backlog, this has the clearest existing technical foundation to build from (`list_memories()` already does the pagination work) — flagged as comparatively low-effort if ever prioritized, without implying it currently is. |

## Accessibility & Inclusion Cluster

### Adaptive UI

| Field | Value |
|---|---|
| **Idea** | An interface that adapts its complexity, density, and interaction model to the individual user, rather than presenting the same experience to everyone. |
| **Problem Solved** | A single fixed UI inevitably underserves some users (too complex for some, too sparse for power users) — a known, general product tension. |
| **Why It Matters** | Directly serves the platform's inclusivity ambitions, and is a natural complement to Low-literacy Experience and Accessibility Experience below. |
| **Priority** | Low |
| **Dependencies** | Personal Intelligence (CP-01) — user modeling that already exists could plausibly inform adaptation |
| **Potential Capability Pack** | Unclear — likely a frontend/platform concern rather than a Capability Pack in the current sense |
| **Suggested Version** | Post-v2 |
| **Status** | Idea |
| **Notes** | This platform's Capability Pack model is backend-oriented; this idea may not map onto "Capability Pack" cleanly at all and may need its own categorization when seriously scoped. |

### Accessibility Experience

| Field | Value |
|---|---|
| **Idea** | First-class support for users with visual, auditory, motor, or cognitive accessibility needs, across the whole platform. |
| **Problem Solved** | Accessibility has not yet been a designed-for dimension anywhere in the current architecture. |
| **Why It Matters** | A baseline inclusivity commitment, not a differentiator — and directly reinforced by Voice Conversation Mode and Adaptive UI, both already in this backlog. |
| **Priority** | Medium |
| **Dependencies** | Voice Conversation Mode, Adaptive UI |
| **Potential Capability Pack** | Unclear — likely a cross-cutting concern rather than a single pack |
| **Suggested Version** | Post-v1 |
| **Status** | Idea |
| **Notes** | Worth an early, dedicated PRD even before other items in this cluster, given how foundational accessibility usually is to get right early rather than retrofit. |

### Low-literacy Experience

| Field | Value |
|---|---|
| **Idea** | An experience designed for users with limited reading/writing literacy — voice-first, icon-driven, minimal text dependency. |
| **Problem Solved** | The platform today is entirely text-mediated; this excludes a real, large population the Master Blueprint's inclusivity ambitions explicitly aim to reach. |
| **Why It Matters** | A precondition for Market Trader Experience and Farmer Experience being genuinely usable by their intended audiences, not just accessible in theory. |
| **Priority** | Medium |
| **Dependencies** | Voice Conversation Mode, Universal Language Layer |
| **Potential Capability Pack** | Unclear |
| **Suggested Version** | Post-v2 |
| **Status** | Idea |
| **Notes** | None |

## Health Intelligence Cluster

This cluster was registered following a real-world experience involving delayed emergency response during a family medical emergency — the kind of moment that makes plain how much difference organized information, calm guidance, and prompt action can make when it matters most. It is captured here at idea stage only, exactly like every other cluster in this document: a long-term direction the platform has explicitly committed to remembering, not a scheduled body of work.

**Philosophy alignment**: [PRODUCT_PHILOSOPHY_FREEZE_v1.md](PRODUCT_PHILOSOPHY_FREEZE_v1.md) §3 (Mission) states that this platform exists to help people "make better decisions — every day." Health is one of the highest-stakes everyday decision domains a person ever faces, and one where the gap between "informed and prepared" and "not" is measured in outcomes, not convenience. §6 (Universal Accessibility) already names the platform's obligation to be usable "without compromise, by executives, students, developers, teachers, traders, market women, farmers, artisans, elderly users, and children" — precisely the range this cluster's long-term vision targets: a market trader, a farmer, an elderly person, a young parent, someone living alone, all deserve the same quality of health support as anyone with a personal physician on call, without implying any of this has an implementation timeline. [MASTER_BLUEPRINT.md](MASTER_BLUEPRINT.md) §15 already names Healthcare as a future capability pack, and is explicit and binding on everything below: "always in a clearly supportive, non-diagnostic role, and held to the strictest application of the platform's privacy, sensitivity, and retention principles of any pack that will ever exist... because health data carries a duty of care no other data category on this platform matches." Nothing in this cluster proposes anything other than a concrete elaboration of that already-approved paragraph — no new philosophical stance is introduced. **This platform never replaces licensed medical professionals**, in any capability named below, without exception.

### Health Intelligence Pack (CP-08) (umbrella)

| Field | Value |
|---|---|
| **Idea** | A lifelong AI health companion focused on prevention, organization, emergency preparedness, wellness coaching, and collaboration with healthcare professionals — never a replacement for doctors. |
| **Problem Solved** | Health information today is scattered across memory, paper, and disconnected apps; people are least organized and least calm exactly when a medical situation (routine or urgent) most rewards being both. |
| **Why It Matters** | Health is one of the platform's most consequential "everyday decision" domains (Product Philosophy Freeze §3); this pack would help people understand their health better, prepare for appointments, maintain healthier habits, organize medical information, respond better during emergencies, and collaborate more effectively with healthcare professionals. |
| **Priority** | High Strategic Value |
| **Dependencies** | Personal Intelligence (CP-01, identity/preference/reflection foundation), Memory Framework, a concrete Conversation provider, and — for emergency scenarios specifically — real-time/streaming support (shared with Live Meeting Assistant's own dependency, Meeting Intelligence Cluster) |
| **Potential Capability Pack** | New Pack — **CP-08**, registered in [Capability_Strategy.md](08_CAPABILITY_PACKS/Capability_Strategy.md)'s Numbering Convention as a reserved future identifier, elaborating Master Blueprint §15's already-named "Healthcare" direction |
| **Suggested Version** | Post-v1 |
| **Status** | Future Vision |
| **Notes** | Execution Status: Not Scheduled. Implementation Status: Not Started. Roadmap Status: Backlog Only. The six specialists below were named alongside it and are treated as its likely first specialists rather than independent packs, pending a real PRD — mirroring exactly how the Meeting Intelligence cluster's own umbrella/specialist relationship is recorded above. |

### Health Profile Specialist

| Field | Value |
|---|---|
| **Idea** | Maintains a person's core health record: medical history, allergies, medications, blood group, genotype, family history, and chronic illnesses. |
| **Problem Solved** | This information is exactly what a person is least likely to have organized and instantly recallable in the moment it's needed — a new doctor visit, an emergency, a pharmacy interaction. |
| **Why It Matters** | The foundational record every other Health Intelligence specialist below reads from, the same architectural role CP-01's own identity/goal memory plays for every other pack that builds on it. |
| **Priority** | High Strategic Value |
| **Dependencies** | Health Intelligence Pack (CP-08), Memory Framework |
| **Potential Capability Pack** | Health Intelligence Pack (CP-08) |
| **Suggested Version** | Post-v1 |
| **Status** | Future Vision |
| **Notes** | Execution Status: Not Scheduled. Implementation Status: Not Started. Roadmap Status: Backlog Only. |

### Wellness Specialist

| Field | Value |
|---|---|
| **Idea** | Supports sleep, exercise, hydration, stress, preventive care, and daily wellness habits. |
| **Problem Solved** | Preventive, day-to-day wellness guidance today is generic (a fitness app, a sleep app) rather than grounded in a specific person's actual health profile and goals. |
| **Why It Matters** | Prevention is the highest-leverage, lowest-cost form of health support this pack could offer — keeping people well is a different (and different-in-kind) problem from helping them once something has already gone wrong. |
| **Priority** | High Strategic Value |
| **Dependencies** | Health Intelligence Pack (CP-08), Health Profile Specialist, Personal Intelligence (CP-01, goals/reflection) |
| **Potential Capability Pack** | Health Intelligence Pack (CP-08) |
| **Suggested Version** | Post-v1 |
| **Status** | Future Vision |
| **Notes** | Execution Status: Not Scheduled. Implementation Status: Not Started. Roadmap Status: Backlog Only. |

### Nutrition Specialist

| Field | Value |
|---|---|
| **Idea** | Context-aware meal planning based on country, culture, religion, budget, food availability, doctor guidance, allergies, and dietary restrictions. |
| **Problem Solved** | Generic nutrition advice ignores the real constraints that determine whether guidance is actually usable — what's affordable, what's available locally, and what a person's culture or faith permits. |
| **Why It Matters** | A direct expression of this platform's inclusivity commitment (Product Philosophy Freeze §6, Master Blueprint §16) applied to health specifically — the same meal-planning question deserves a different, equally rigorous answer for a market trader in one country and a remote worker in another. |
| **Priority** | High Strategic Value |
| **Dependencies** | Health Intelligence Pack (CP-08), Health Profile Specialist (allergies/restrictions/doctor guidance) |
| **Potential Capability Pack** | Health Intelligence Pack (CP-08) |
| **Suggested Version** | Post-v1 |
| **Status** | Future Vision |
| **Notes** | Execution Status: Not Scheduled. Implementation Status: Not Started. Roadmap Status: Backlog Only. |

### Emergency Response Specialist

| Field | Value |
|---|---|
| **Idea** | Evidence-based emergency guidance — covering scenarios such as CPR, heart attack recognition, stroke recognition, choking, bleeding, burns, fractures, seizures, allergic reactions, poisoning, and fainting — while continuously instructing users to contact local emergency services or proceed to the nearest hospital when appropriate. |
| **Problem Solved** | The exact real-world gap this cluster was registered from: in a medical emergency, people are least equipped, in the moment, to recall correct guidance or act with a clear head — and delay or the wrong action can materially worsen an outcome. |
| **Why It Matters** | The single highest-stakes capability in this entire backlog. It must never be built casually: every guidance path is evidence-based, and the specialist's own posture is to keep directing the person toward real emergency services and real medical care, never to position itself as a substitute for either. |
| **Priority** | High Strategic Value |
| **Dependencies** | Health Intelligence Pack (CP-08), Health Profile Specialist (allergies/conditions relevant to triage), Emergency Intelligence (below, the cross-platform capability this specialist would be the CP-08-specific expression of) |
| **Potential Capability Pack** | Health Intelligence Pack (CP-08) |
| **Suggested Version** | Post-v1 |
| **Status** | Future Vision |
| **Notes** | Execution Status: Not Scheduled. Implementation Status: Not Started. Roadmap Status: Backlog Only. Given the stakes, this specialist should be held, whenever it is eventually scoped, to a materially higher evidentiary and review bar than an ordinary Phase 1 PRD — a note for whoever picks this up, not a process this document has the authority to mandate. |

### Doctor Collaboration Specialist

| Field | Value |
|---|---|
| **Idea** | Helps users prepare structured medical summaries for healthcare professionals — a symptom timeline, medication history, questions for the doctor, and appointment preparation. |
| **Problem Solved** | Appointments are short and people forget what they meant to ask or mention; a doctor without an organized history is working with less than they need. |
| **Why It Matters** | Directly serves this pack's own stated purpose of helping people "collaborate more effectively with healthcare professionals" — this platform organizes and prepares, the doctor still decides. |
| **Priority** | High Strategic Value |
| **Dependencies** | Health Intelligence Pack (CP-08), Health Profile Specialist |
| **Potential Capability Pack** | Health Intelligence Pack (CP-08) |
| **Suggested Version** | Post-v1 |
| **Status** | Future Vision |
| **Notes** | Execution Status: Not Scheduled. Implementation Status: Not Started. Roadmap Status: Backlog Only. |

### Health Companion Specialist

| Field | Value |
|---|---|
| **Idea** | Supports medication reminders, appointment reminders, health journaling, recovery tracking, and vital-trend summaries. |
| **Problem Solved** | The ongoing, unglamorous logistics of managing one's own or a family member's health — the reason regimens lapse and follow-ups get missed isn't lack of care, it's lack of a reliable, persistent system. |
| **Why It Matters** | The companion-relationship expression of health support (Product Philosophy Freeze §8) — showing up consistently over months and years is exactly the kind of reliability this platform is built to provide. |
| **Priority** | High Strategic Value |
| **Dependencies** | Health Intelligence Pack (CP-08), Health Profile Specialist, Wellness Specialist |
| **Potential Capability Pack** | Health Intelligence Pack (CP-08) |
| **Suggested Version** | Post-v1 |
| **Status** | Future Vision |
| **Notes** | Execution Status: Not Scheduled. Implementation Status: Not Started. Roadmap Status: Backlog Only. |

### Health Companion Wearable

| Field | Value |
|---|---|
| **Idea** | A future hardware product: a lightweight bracelet or similar unobtrusive accessory that continuously gathers health signals and securely shares them with the AI Operating System. |
| **Problem Solved** | Health Intelligence Pack reasoning is only as good as the signal it has to reason over — much of the most useful health information (vitals trends, activity, sleep) is otherwise only available second-hand, self-reported, or not at all. |
| **Why It Matters** | Described strictly at the product-vision level: **the wearable is not the intelligence, the wearable is the sensor** — the AI Operating System remains the one and only reasoning engine, exactly as every other capability pack's relationship to a future concrete device or provider already works (Vision Framework, Tool Framework). No hardware implementation is described or implied here. |
| **Priority** | High Strategic Value |
| **Dependencies** | Health Intelligence Pack (CP-08), a secure device-to-platform data channel (no such mechanism exists on the platform today, and none is proposed here) |
| **Potential Capability Pack** | Health Intelligence Pack (CP-08) — a future sensor/data source it would consume, not a specialist or a pack of its own |
| **Suggested Version** | Post-v2 |
| **Status** | Future Vision |
| **Notes** | Execution Status: Not Scheduled. Implementation Status: Not Started. Roadmap Status: Backlog Only. Product-vision only, deliberately — no hardware design, protocol, or device architecture is proposed anywhere in this entry. |

### Emergency Intelligence

| Field | Value |
|---|---|
| **Idea** | A future **platform capability**, not a standalone product: helping users respond more effectively during emergencies by recognizing potential emergencies, providing evidence-based first-aid guidance, helping users notify trusted contacts (where configured), preparing information for healthcare professionals, and encouraging immediate contact with emergency services whenever appropriate. |
| **Problem Solved** | Emergency-relevant reasoning (recognizing what's happening, knowing what to do in the first minute, getting the right information to the right people) is a capability multiple future packs would need, not something that belongs siloed inside Health Intelligence alone. |
| **Why It Matters** | The cross-cutting foundation the Emergency Response Specialist (above) would be the Health Intelligence Pack's own concrete expression of — mirroring exactly how Voice Conversation Mode (Language Cluster) is a cross-cutting enabler multiple packs would consume, not owned by any single one. **The platform never replaces licensed medical professionals** — every path through this capability continues directing the user toward real emergency services and real medical care. |
| **Priority** | High Strategic Value |
| **Dependencies** | Voice Conversation Mode (for hands-free use during an actual emergency), real-time/streaming infrastructure, a trusted-contacts notification mechanism (does not exist on the platform today) |
| **Potential Capability Pack** | Unclear — cross-cutting platform capability, likely consumed by Health Intelligence (CP-08) and potentially others, not owned by a single pack, the same treatment Voice Conversation Mode already receives above |
| **Suggested Version** | Post-v2 |
| **Status** | Future Vision |
| **Notes** | Execution Status: Not Scheduled. Implementation Status: Not Started. Roadmap Status: Backlog Only. Given the stakes, this capability carries the identical elevated-review note as the Emergency Response Specialist above. |

---

## How Ideas Move

An idea leaves this backlog in exactly one of three ways:

1. **Graduates** — a PRD is written for it (Phase 1 of the Development Guide); it is removed from this file and its status begins tracking in [CAPABILITY_READINESS.md](CAPABILITY_READINESS.md) at CRL-0/CRL-1 instead.
2. **Superseded** — a later idea or a graduated capability already covers it; its Status here changes to Superseded with a note pointing to what replaced it, and it stays for historical record.
3. **Rejected** — explicitly decided against, with a one-line reason recorded in Notes; kept, not deleted, so the reasoning isn't lost and the idea isn't accidentally re-proposed without knowing it was already considered.

Nothing in this document authorizes design or implementation work. It is a record of vision, deliberately kept separate from commitment.
