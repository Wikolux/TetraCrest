"""Every plain, closed-taxonomy enum used across the Agent Framework.

Centralized here rather than split across state.py/events.py/messages.py/
capabilities.py: each of those files owns the richer logic/dataclasses
built around one of these enums, but the enum values themselves are pure,
dependency-free leaf data every one of those files (and tests) can import
from a single place without risking a circular import.
"""

from enum import StrEnum


class AgentState(StrEnum):
    """Where an agent is in its lifecycle - the agent-framework analogue
    of an OS process's state (new/ready/running/waiting/terminated).
    """

    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"
    STOPPED = "stopped"


class AgentEventType(StrEnum):
    """Every kind of lifecycle event an agent can emit."""

    CREATED = "created"
    INITIALIZED = "initialized"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    RESUMED = "resumed"
    CANCELLED = "cancelled"
    SHUTDOWN = "shutdown"


class MessageType(StrEnum):
    """What kind of thing an AgentMessage represents."""

    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    COMMAND = "command"
    ERROR = "error"


class MessagePriority(StrEnum):
    """How urgently an AgentMessage should be handled."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AgentCapability(StrEnum):
    """What kind of thing an agent supports - describes the agent itself,
    never a provider (see app.services.ai.shared.types.ProviderCapabilities
    for that)."""

    MEMORY = "memory"
    TOOLS = "tools"
    RESEARCH = "research"
    REASONING = "reasoning"
    PLANNING = "planning"
    COMMUNICATION = "communication"
    VISION = "vision"
    VOICE = "voice"
    FILES = "files"
    WORKFLOWS = "workflows"
