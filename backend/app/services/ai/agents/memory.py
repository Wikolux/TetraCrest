"""AgentMemory - the abstraction an agent uses to remember things.

Every method is abstract - there is no sensible default for "how does this
agent remember/forget/search."

Concrete implementation: app.services.ai.agents.specialists.memory_adapter.MemoryAdapter
adapts this contract onto MemoryRetrievalPipeline (retrieve()/search()) -
see that module's docstring for what is and isn't wired (remember()/
forget() have no backing write-path today and raise NotImplementedError).
"""

from abc import ABC, abstractmethod
from typing import Any


class AgentMemory(ABC):
    @abstractmethod
    def remember(self, item: Any, **kwargs: Any) -> None:
        """Persist something this agent should be able to recall later."""
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, query: str, **kwargs: Any) -> Any:
        """Recall whatever is most relevant to query."""
        raise NotImplementedError

    @abstractmethod
    def forget(self, item_id: str) -> None:
        """Remove a previously remembered item."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, **kwargs: Any) -> Any:
        """Search across everything this agent has remembered."""
        raise NotImplementedError
