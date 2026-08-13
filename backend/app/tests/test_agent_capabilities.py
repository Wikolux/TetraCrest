import dataclasses

import pytest

from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.enums import AgentCapability


def test_defaults_to_no_declared_capabilities():
    capabilities = AgentCapabilities()

    assert capabilities.declared == frozenset()
    assert capabilities.has(AgentCapability.MEMORY) is False


def test_has_reflects_declared_capabilities():
    capabilities = AgentCapabilities(declared={AgentCapability.MEMORY, AgentCapability.TOOLS})

    assert capabilities.has(AgentCapability.MEMORY) is True
    assert capabilities.has(AgentCapability.TOOLS) is True
    assert capabilities.has(AgentCapability.VISION) is False


def test_declared_is_coerced_to_a_real_frozenset_from_a_list():
    capabilities = AgentCapabilities(declared=[AgentCapability.MEMORY])

    assert isinstance(capabilities.declared, frozenset)


def test_declared_frozenset_cannot_be_mutated_through_the_instance():
    capabilities = AgentCapabilities(declared={AgentCapability.MEMORY})

    with pytest.raises(AttributeError):
        capabilities.declared.add(AgentCapability.TOOLS)


def test_agent_capabilities_is_frozen():
    capabilities = AgentCapabilities()

    with pytest.raises(dataclasses.FrozenInstanceError):
        capabilities.declared = frozenset()
