"""DiscoveryRequest - what a caller asks the Discovery Specialist to do.

Not a duplicate of SpecialistRequest (app.services.ai.agents.specialists.shared.request)
- that type is the Specialist Framework's generic, cross-domain request
shape, with no slot for "which structured Discovery operation" or the
typed hints (source, hypothesis, status, jobs/pains/goals, ...) Discovery's
twelve operations need. Building a pack-local request type when the
shared generic genuinely doesn't fit is the same, sanctioned pattern
PersonalIntelligenceRequest already follows (personal_intelligence/shared/request.py)
- see docs/08_CAPABILITY_PACKS/CP-02_Product_Management_Intelligence_Pack/Architecture.md §8.

The operation set maps directly onto this milestone's required
capabilities and PRD §15's Discovery Capabilities:

- VALIDATE_PROBLEM, SYNTHESIZE_INTERVIEW, TRACK_HYPOTHESIS: record evidence
  (write a DiscoveryFinding).
- FRAME_JTBD, FRAME_PERSONA, ASSESS_OPPORTUNITY: structured reasoning
  frames, informed by retrieved precedent, never evidence records of their
  own.
- GENERATE_RECOMMENDATION: evidence-backed recommendation synthesis.
- RUN_DISCOVERY_SESSION: the PRD §9.1 representative journey end to end -
  problem framing, hypotheses, evidence gaps, in one structured report.
- SUMMARIZE: a lighter-weight "what do we know so far" view over the
  existing corpus (list_by_memory_type-backed).
- FRAME_RESEARCH_QUESTION: frames a question for the Executive to delegate
  to ResearchAgent (Architecture §9) - never invokes ResearchAgent itself.
- RECORD_RESEARCH_FINDING: records findings handed back after a delegated
  ResearchAgent turn completes (Architecture §9, sequential shape).
- RECALL: discovery memory retrieval, mirroring PersonalIntelligenceAgent's
  own RECALL operation.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class DiscoveryOperation(StrEnum):
    VALIDATE_PROBLEM = "validate_problem"
    FRAME_JTBD = "frame_jtbd"
    SYNTHESIZE_INTERVIEW = "synthesize_interview"
    ASSESS_OPPORTUNITY = "assess_opportunity"
    FRAME_PERSONA = "frame_persona"
    TRACK_HYPOTHESIS = "track_hypothesis"
    GENERATE_RECOMMENDATION = "generate_recommendation"
    RUN_DISCOVERY_SESSION = "run_discovery_session"
    SUMMARIZE = "summarize"
    FRAME_RESEARCH_QUESTION = "frame_research_question"
    RECORD_RESEARCH_FINDING = "record_research_finding"
    RECALL = "recall"


@dataclass(frozen=True)
class DiscoveryRequest:
    operation: DiscoveryOperation
    text: str = ""
    title: str = ""
    source: str = ""
    hypothesis: str = ""
    status: str = ""
    source_question: str = ""
    implications: str = ""
    informs: str = ""
    segment: str = ""
    jobs: tuple[str, ...] = field(default_factory=tuple)
    pains: tuple[str, ...] = field(default_factory=tuple)
    goals: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("jobs", "pains", "goals"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
