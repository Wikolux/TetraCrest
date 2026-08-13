"""Agent-to-agent communication as pure value objects.

No networking, no queues, no delivery mechanism - AgentMessage/
AgentEnvelope only describe the shape of a message and its envelope. A
future AgentOrchestrator implementation is what would actually move these
between agents.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from app.services.ai.agents.enums import MessagePriority, MessageType
from app.services.ai.agents.types import Metadata


def _freeze_mapping(instance, field_name: str) -> None:
    value = getattr(instance, field_name)
    if not isinstance(value, MappingProxyType):
        object.__setattr__(instance, field_name, MappingProxyType(dict(value)))


@dataclass(frozen=True)
class AgentMessage:
    """One unit of communication between agents."""

    sender_id: str
    message_type: MessageType
    recipient_id: str | None = None
    priority: MessagePriority = MessagePriority.NORMAL
    payload: Any = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_mapping(self, "metadata")


@dataclass(frozen=True)
class AgentEnvelope:
    """Wraps an AgentMessage for delivery - envelope-level metadata (e.g.
    routing hints) stays separate from the message's own content."""

    message: AgentMessage
    envelope_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_mapping(self, "metadata")
