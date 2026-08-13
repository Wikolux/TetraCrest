"""PersonalMemoryService - a thin, domain-typed wrapper over AgentMemory.

Never reimplements storage or retrieval: every method here does exactly
one thing - render a CP-01 domain value object to natural-language memory
content (each object's own to_memory_content(), already written for
semantic retrievability) and call AgentMemory.remember()/retrieve() with
it. This is the same "thin adapter, zero new logic" pattern
MemoryAdapter/ToolAdapter/RuntimeAdapter already establish - not a
second, competing memory abstraction.

Defaults to constructing a MemoryAdapter (the platform's only concrete
AgentMemory), but is typed against AgentMemory itself so a fake is trivial
to inject in tests, and so PersonalIntelligenceAgent never depends on a
concrete adapter type - the same reasoning already applied to
SpecialistCoordinator.memory_adapter (see coordinator.py).
"""

from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.personal_intelligence.shared.goal import Goal, GoalProgressUpdate
from app.services.ai.agents.specialists.personal_intelligence.shared.identity import IdentityFact
from app.services.ai.agents.specialists.personal_intelligence.shared.preference import Preference
from app.services.ai.agents.specialists.personal_intelligence.shared.project import Project
from app.services.ai.agents.specialists.personal_intelligence.shared.reflection import Reflection
from app.services.context.types import ContextPackage

_DEFAULT_LIMIT = 10
_DEFAULT_MAX_CONTEXT_TOKENS = 4000


class PersonalMemoryService:
    def __init__(self, memory: AgentMemory | None = None) -> None:
        self.memory = memory or MemoryAdapter()

    # --- write side --------------------------------------------------------------------------

    def remember_identity(self, fact: IdentityFact, *, organization_id: int, user_id: int | None = None) -> None:
        self._remember(fact.to_memory_content(), fact.memory_type, fact.title(), organization_id, user_id)

    def remember_goal(self, goal: Goal, *, organization_id: int, user_id: int | None = None) -> None:
        self._remember(goal.to_memory_content(), goal.memory_type, goal.title, organization_id, user_id)

    def remember_goal_progress(
        self, update: GoalProgressUpdate, *, organization_id: int, user_id: int | None = None
    ) -> None:
        title = f"Progress: {update.goal_title}"
        self._remember(update.to_memory_content(), update.memory_type, title, organization_id, user_id)

    def remember_project(self, project: Project, *, organization_id: int, user_id: int | None = None) -> None:
        self._remember(project.to_memory_content(), project.memory_type, project.name, organization_id, user_id)

    def remember_reflection(self, reflection: Reflection, *, organization_id: int, user_id: int | None = None) -> None:
        title = f"Reflection ({reflection.period.value})"
        self._remember(reflection.to_memory_content(), reflection.memory_type, title, organization_id, user_id)

    def remember_preference(self, preference: Preference, *, organization_id: int, user_id: int | None = None) -> None:
        title = f"Preference ({preference.category})"
        self._remember(preference.to_memory_content(), preference.memory_type, title, organization_id, user_id)

    def _remember(self, content: str, memory_type: str, title: str, organization_id: int, user_id: int | None) -> None:
        self.memory.remember(
            content, organization_id=organization_id, user_id=user_id, memory_type=memory_type, title=title
        )

    # --- read side ----------------------------------------------------------------------------

    def recall(
        self,
        query: str,
        *,
        organization_id: int,
        limit: int = _DEFAULT_LIMIT,
        max_context_tokens: int = _DEFAULT_MAX_CONTEXT_TOKENS,
    ) -> ContextPackage:
        """Semantic recall across everything this pack has remembered for
        this organization - scope="memories", since Personal Intelligence
        data is never stored as a conversation message."""
        return self.memory.retrieve(
            query,
            organization_id=organization_id,
            scope="memories",
            limit=limit,
            max_context_tokens=max_context_tokens,
        )
