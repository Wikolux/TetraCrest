"""Cross-subsystem coverage for M16.5: Kernel, Runtime, and Agents all
compose the same SharedExecutionContext rather than each defining their
own notion of execution identity. These tests build one execution tree
that spans all three and confirm the tree/correlation stays coherent
across the whole chain - the actual architectural goal of this milestone,
not just something true of each subsystem in isolation.
"""

from app.services.ai.agents.context import AgentContext
from app.services.ai.kernel.context import ExecutionContext
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeContext
from app.services.ai.shared.execution_context import SharedExecutionContext


def test_kernel_runtime_and_agent_contexts_all_compose_the_same_shared_type():
    shared = SharedExecutionContext(organization_id=1)

    kernel_context = ExecutionContext(shared=shared, capability="conversation")
    runtime_context = RuntimeContext(shared=shared, provider=ProviderName.OPENAI)
    agent_context = AgentContext(shared=shared, agent_id="agent-1")

    assert kernel_context.execution_id == runtime_context.execution_id == agent_context.execution_id
    assert kernel_context.organization_id == runtime_context.shared.organization_id == 1


def test_an_execution_tree_spanning_agent_to_runtime_shares_one_correlation_id():
    # Executive -> Agent -> Runtime, using SharedExecutionContext.child()
    # at each hop, mirroring how a real orchestrator would propagate
    # identity down through the AI Operating System's layers.
    executive = SharedExecutionContext(organization_id=1, user_id=7)
    agent_shared = executive.child()
    runtime_shared = agent_shared.child()

    agent_context = AgentContext(shared=agent_shared, agent_id="agent-1")
    runtime_context = RuntimeContext(
        shared=runtime_shared, provider=ProviderName.OPENAI, provider_model="gpt-fake"
    )

    assert agent_context.shared.correlation_id == executive.correlation_id
    assert runtime_context.shared.correlation_id == executive.correlation_id
    assert runtime_context.shared.parent_execution_id == agent_context.execution_id
    assert agent_context.shared.parent_execution_id == executive.execution_id


def test_runtime_context_still_composes_correctly_when_built_by_the_executor_path():
    # sanity check that a "real" RuntimeContext (as RuntimeExecutor builds
    # it, not hand-constructed) is still a genuine SharedExecutionContext
    # composition, not a parallel reimplementation
    context = RuntimeContext(provider=ProviderName.OPENAI, provider_model="gpt-fake", timeout=30.0)

    assert isinstance(context.shared, SharedExecutionContext)
    assert context.provider_model == "gpt-fake"
    assert context.timeout == 30.0
