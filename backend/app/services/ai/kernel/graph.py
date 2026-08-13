from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.kernel.types import Metadata


def _freeze_metadata(instance) -> None:
    if not isinstance(instance.metadata, MappingProxyType):
        object.__setattr__(instance, "metadata", MappingProxyType(dict(instance.metadata)))


@dataclass(frozen=True)
class ExecutionNode:
    """One node in an execution graph.

    An opaque unit of execution identified by node_id - the graph makes
    no assumption about what a node represents (a capability call, a
    provider call, a step in a future multi-step workflow, ...). That's
    exactly what "no execution logic" means here: identity and metadata
    only, nothing about what running this node would do.
    """

    node_id: str
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_metadata(self)


@dataclass(frozen=True)
class ExecutionEdge:
    """A directed relationship between two ExecutionNodes.

    References nodes by node_id, not by object, so a graph can be built
    or described without holding live node references.
    """

    source_id: str
    target_id: str
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_metadata(self)


@dataclass(frozen=True)
class ExecutionGraph:
    """A generic directed graph of ExecutionNodes and ExecutionEdges.

    Represents execution *relationships* only - which unit of work
    follows or depends on which - never what those units of work
    actually do, and never how or whether they run. No traversal
    strategy, scheduling, or execution logic lives here; this is pure
    structure, capability- and provider-agnostic by construction (nodes
    and edges carry only ids and generic metadata).

    __post_init__ validates that every edge references nodes that
    actually exist in this graph - structural integrity, not execution
    logic.
    """

    nodes: tuple[ExecutionNode, ...] = field(default_factory=tuple)
    edges: tuple[ExecutionEdge, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        node_ids = {node.node_id for node in self.nodes}
        for edge in self.edges:
            if edge.source_id not in node_ids:
                raise ValueError(f"ExecutionEdge references unknown source node: {edge.source_id!r}")
            if edge.target_id not in node_ids:
                raise ValueError(f"ExecutionEdge references unknown target node: {edge.target_id!r}")

    def get_node(self, node_id: str) -> ExecutionNode | None:
        return next((node for node in self.nodes if node.node_id == node_id), None)

    def outgoing_edges(self, node_id: str) -> tuple[ExecutionEdge, ...]:
        return tuple(edge for edge in self.edges if edge.source_id == node_id)

    def incoming_edges(self, node_id: str) -> tuple[ExecutionEdge, ...]:
        return tuple(edge for edge in self.edges if edge.target_id == node_id)
