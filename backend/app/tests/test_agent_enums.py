from app.services.ai.agents.enums import AgentCapability, AgentEventType, AgentState, MessagePriority, MessageType


def test_agent_state_has_every_documented_value():
    assert {member.value for member in AgentState} == {
        "created",
        "initializing",
        "ready",
        "running",
        "waiting",
        "paused",
        "cancelled",
        "failed",
        "stopped",
    }


def test_agent_event_type_has_every_documented_value():
    assert {member.value for member in AgentEventType} == {
        "created",
        "initialized",
        "started",
        "completed",
        "failed",
        "paused",
        "resumed",
        "cancelled",
        "shutdown",
    }


def test_message_type_has_every_documented_value():
    assert {member.value for member in MessageType} == {"request", "response", "event", "command", "error"}


def test_message_priority_has_every_documented_value():
    assert {member.value for member in MessagePriority} == {"low", "normal", "high", "critical"}


def test_agent_capability_has_every_documented_value():
    assert {member.value for member in AgentCapability} == {
        "memory",
        "tools",
        "research",
        "reasoning",
        "planning",
        "communication",
        "vision",
        "voice",
        "files",
        "workflows",
    }
