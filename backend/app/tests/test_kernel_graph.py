import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.kernel.graph import ExecutionEdge, ExecutionGraph, ExecutionNode


# --- ExecutionNode -------------------------------------------------------------


def test_execution_node_construction():
    node = ExecutionNode(node_id="a", metadata={"kind": "capability_call"})

    assert node.node_id == "a"
    assert node.metadata == {"kind": "capability_call"}


def test_execution_node_metadata_defaults_to_empty_read_only_mapping():
    node = ExecutionNode(node_id="a")

    assert isinstance(node.metadata, MappingProxyType)
    assert dict(node.metadata) == {}


def test_execution_node_metadata_cannot_be_mutated():
    node = ExecutionNode(node_id="a", metadata={"x": 1})

    with pytest.raises(TypeError):
        node.metadata["x"] = 2


def test_execution_node_is_frozen():
    node = ExecutionNode(node_id="a")

    with pytest.raises(dataclasses.FrozenInstanceError):
        node.node_id = "b"


# --- ExecutionEdge -------------------------------------------------------------


def test_execution_edge_construction():
    edge = ExecutionEdge(source_id="a", target_id="b")

    assert edge.source_id == "a"
    assert edge.target_id == "b"


def test_execution_edge_metadata_cannot_be_mutated():
    edge = ExecutionEdge(source_id="a", target_id="b", metadata={"x": 1})

    with pytest.raises(TypeError):
        edge.metadata["x"] = 2


def test_execution_edge_is_frozen():
    edge = ExecutionEdge(source_id="a", target_id="b")

    with pytest.raises(dataclasses.FrozenInstanceError):
        edge.source_id = "c"


# --- ExecutionGraph -----------------------------------------------------------


def test_execution_graph_defaults_to_empty():
    graph = ExecutionGraph()

    assert graph.nodes == ()
    assert graph.edges == ()


def test_execution_graph_construction():
    node_a = ExecutionNode(node_id="a")
    node_b = ExecutionNode(node_id="b")
    edge = ExecutionEdge(source_id="a", target_id="b")

    graph = ExecutionGraph(nodes=(node_a, node_b), edges=(edge,))

    assert graph.nodes == (node_a, node_b)
    assert graph.edges == (edge,)


def test_execution_graph_rejects_edge_with_unknown_source():
    node_b = ExecutionNode(node_id="b")

    with pytest.raises(ValueError, match="source"):
        ExecutionGraph(nodes=(node_b,), edges=(ExecutionEdge(source_id="missing", target_id="b"),))


def test_execution_graph_rejects_edge_with_unknown_target():
    node_a = ExecutionNode(node_id="a")

    with pytest.raises(ValueError, match="target"):
        ExecutionGraph(nodes=(node_a,), edges=(ExecutionEdge(source_id="a", target_id="missing"),))


def test_execution_graph_get_node_returns_matching_node():
    node_a = ExecutionNode(node_id="a")
    graph = ExecutionGraph(nodes=(node_a,))

    assert graph.get_node("a") is node_a


def test_execution_graph_get_node_returns_none_when_missing():
    graph = ExecutionGraph()

    assert graph.get_node("missing") is None


def test_execution_graph_outgoing_edges():
    node_a, node_b, node_c = ExecutionNode(node_id="a"), ExecutionNode(node_id="b"), ExecutionNode(node_id="c")
    edge_ab = ExecutionEdge(source_id="a", target_id="b")
    edge_ac = ExecutionEdge(source_id="a", target_id="c")
    graph = ExecutionGraph(nodes=(node_a, node_b, node_c), edges=(edge_ab, edge_ac))

    assert graph.outgoing_edges("a") == (edge_ab, edge_ac)
    assert graph.outgoing_edges("b") == ()


def test_execution_graph_incoming_edges():
    node_a, node_b, node_c = ExecutionNode(node_id="a"), ExecutionNode(node_id="b"), ExecutionNode(node_id="c")
    edge_ac = ExecutionEdge(source_id="a", target_id="c")
    edge_bc = ExecutionEdge(source_id="b", target_id="c")
    graph = ExecutionGraph(nodes=(node_a, node_b, node_c), edges=(edge_ac, edge_bc))

    assert graph.incoming_edges("c") == (edge_ac, edge_bc)
    assert graph.incoming_edges("a") == ()


def test_execution_graph_is_frozen():
    graph = ExecutionGraph()

    with pytest.raises(dataclasses.FrozenInstanceError):
        graph.nodes = (ExecutionNode(node_id="a"),)


def test_execution_graph_nodes_and_edges_are_tuples():
    graph = ExecutionGraph(nodes=(ExecutionNode(node_id="a"),))

    assert isinstance(graph.nodes, tuple)
    assert isinstance(graph.edges, tuple)


def test_execution_graph_knows_nothing_about_capabilities_or_providers():
    # structural check: neither dataclass has a field named after any
    # capability/provider concept - the graph is purely relational
    node_fields = {f.name for f in dataclasses.fields(ExecutionNode)}
    edge_fields = {f.name for f in dataclasses.fields(ExecutionEdge)}

    forbidden = {"capability", "provider", "conversation", "vision", "embedding"}
    assert not (node_fields & forbidden)
    assert not (edge_fields & forbidden)
