"""Preference - a durable statement about how the user wants to be
worked with (response style, scheduling constraints, learning style, ...).

Deliberately a free-text statement, not a fixed key/value pair like
IdentityFact - preferences are naturally expressed as sentences
("I prefer concise answers.") and lose nothing by being stored that way,
whereas identity attributes have a small, known set of dimensions worth
naming explicitly.
"""

from dataclasses import dataclass
from datetime import datetime

from app.services.ai.agents.specialists.personal_intelligence.shared.types import MEMORY_TYPE_PREFERENCE


@dataclass(frozen=True)
class Preference:
    statement: str
    category: str = "general"
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_PREFERENCE

    def to_memory_content(self) -> str:
        return f"User preference ({self.category}): {self.statement}"
