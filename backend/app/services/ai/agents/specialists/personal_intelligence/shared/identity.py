"""IdentityFact - one durable fact about who the user is.

IdentityAttribute is a small, open-in-spirit-but-closed-in-code set of
the identity dimensions CP-01 v1 explicitly captures (name, timezone,
communication style, ...). A fact is always one (attribute, value) pair
rather than one large rigid "profile" object - Memory Framework rows are
independent, retrievable-by-relevance facts, not fields of one row, so
the domain model mirrors that rather than fighting it.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.personal_intelligence.shared.types import MEMORY_TYPE_IDENTITY


class IdentityAttribute(StrEnum):
    NAME = "name"
    PREFERRED_NAME = "preferred_name"
    TIMEZONE = "timezone"
    LANGUAGE = "language"
    LOCATION = "location"
    OCCUPATION = "occupation"
    INTERESTS = "interests"
    COMMUNICATION_STYLE = "communication_style"
    PREFERRED_AI_PERSONALITY = "preferred_ai_personality"
    PREFERRED_RESPONSE_STYLE = "preferred_response_style"


@dataclass(frozen=True)
class IdentityFact:
    attribute: IdentityAttribute
    value: str
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_IDENTITY

    def title(self) -> str:
        return f"Identity: {self.attribute.value.replace('_', ' ')}"

    def to_memory_content(self) -> str:
        """Natural-language rendering - what actually gets embedded and
        semantically retrieved. Deliberately prose, not JSON: embeddings
        are computed over this text, and prose retrieves far better than
        a structured blob for a semantic-memory system with no
        structured-query capability (see Architecture.md §9)."""
        return f"The user's {self.attribute.value.replace('_', ' ')} is: {self.value}."
