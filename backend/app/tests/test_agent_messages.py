import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.enums import MessagePriority, MessageType
from app.services.ai.agents.messages import AgentEnvelope, AgentMessage


def test_agent_message_construction_defaults():
    message = AgentMessage(sender_id="agent-1", message_type=MessageType.REQUEST)

    assert message.sender_id == "agent-1"
    assert message.recipient_id is None
    assert message.priority == MessagePriority.NORMAL
    assert message.payload is None
    assert isinstance(message.message_id, str) and message.message_id


def test_agent_message_two_instances_get_different_ids():
    first = AgentMessage(sender_id="a", message_type=MessageType.EVENT)
    second = AgentMessage(sender_id="a", message_type=MessageType.EVENT)

    assert first.message_id != second.message_id


def test_agent_message_is_frozen():
    message = AgentMessage(sender_id="agent-1", message_type=MessageType.COMMAND)

    with pytest.raises(dataclasses.FrozenInstanceError):
        message.sender_id = "changed"


def test_agent_message_metadata_defaults_to_empty_read_only_mapping():
    message = AgentMessage(sender_id="agent-1", message_type=MessageType.RESPONSE)

    assert isinstance(message.metadata, MappingProxyType)


def test_agent_message_metadata_cannot_be_mutated():
    message = AgentMessage(sender_id="agent-1", message_type=MessageType.ERROR, metadata={"a": 1})

    with pytest.raises(TypeError):
        message.metadata["a"] = 2


def test_agent_envelope_wraps_a_message():
    message = AgentMessage(sender_id="agent-1", message_type=MessageType.REQUEST)

    envelope = AgentEnvelope(message=message)

    assert envelope.message is message
    assert isinstance(envelope.envelope_id, str) and envelope.envelope_id


def test_agent_envelope_is_frozen():
    envelope = AgentEnvelope(message=AgentMessage(sender_id="a", message_type=MessageType.EVENT))

    with pytest.raises(dataclasses.FrozenInstanceError):
        envelope.envelope_id = "changed"


def test_agent_envelope_metadata_cannot_be_mutated():
    envelope = AgentEnvelope(
        message=AgentMessage(sender_id="a", message_type=MessageType.EVENT), metadata={"a": 1}
    )

    with pytest.raises(TypeError):
        envelope.metadata["a"] = 2
