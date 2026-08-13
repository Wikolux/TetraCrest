from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentCapability
from app.services.ai.agents.executive.decision import Decision
from app.services.ai.agents.executive.dispatcher import Dispatcher, required_capabilities
from app.services.ai.agents.executive.task import Task
from app.services.ai.agents.types import AgentIdentity
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeResponse


class _FakeAgent(BaseAgent):
    def __init__(self, name: str, capabilities: AgentCapabilities):
        super().__init__(AgentIdentity(agent_id=name, name=name, display_name=name, capabilities=capabilities))

    def initialize(self) -> None:
        return None

    def execute(self, context: AgentContext) -> RuntimeResponse:
        return RuntimeResponse(success=True)

    def pause(self) -> None:
        return None

    def resume(self) -> None:
        return None

    def cancel(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def health(self) -> bool:
        return True

    def capabilities(self) -> AgentCapabilities:
        return self.identity.capabilities

    def permissions(self) -> tuple[str, ...]:
        return ()

    def memory(self):
        return None

    def planner(self):
        return None

    def runtime(self) -> AIRuntime:
        return AIRuntime()


def _task(**overrides):
    defaults = dict(title="a task", execution_id="exec-1")
    defaults.update(overrides)
    return Task(**defaults)


# --- required_capabilities -----------------------------------------------------------


def test_required_capabilities_empty_when_nothing_required():
    assert required_capabilities(Decision()) == frozenset()


def test_required_capabilities_maps_memory_flag():
    assert required_capabilities(Decision(requires_memory=True)) == {AgentCapability.MEMORY}


def test_required_capabilities_maps_tools_flag():
    assert required_capabilities(Decision(requires_tools=True)) == {AgentCapability.TOOLS}


def test_required_capabilities_maps_web_flag_to_research():
    assert required_capabilities(Decision(requires_web=True)) == {AgentCapability.RESEARCH}


def test_required_capabilities_combines_multiple_flags():
    decision = Decision(requires_memory=True, requires_tools=True)

    assert required_capabilities(decision) == {AgentCapability.MEMORY, AgentCapability.TOOLS}


# --- dispatch --------------------------------------------------------------------------


def test_dispatch_returns_none_when_the_task_requires_no_capability():
    # a Decision-level flag (requires_memory=True) alone must never route
    # a task that doesn't itself carry required_capability - otherwise
    # every task in a plan that "requires_memory" would be routed to a
    # memory-capable agent the moment one is registered, including tasks
    # that have nothing to do with memory.
    dispatcher = Dispatcher()
    memory_agent = _FakeAgent("memory", AgentCapabilities(declared={AgentCapability.MEMORY}))

    result = dispatcher.dispatch(Decision(requires_memory=True), _task(), {"memory": memory_agent})

    assert result is None


def test_dispatch_returns_none_when_no_candidate_has_the_tasks_required_capability():
    dispatcher = Dispatcher()
    research_agent = _FakeAgent("research", AgentCapabilities(declared={AgentCapability.RESEARCH}))
    task = _task(metadata={"required_capability": AgentCapability.MEMORY})

    result = dispatcher.dispatch(Decision(requires_memory=True), task, {"research": research_agent})

    assert result is None


def test_dispatch_matches_a_candidate_by_the_tasks_required_capability():
    dispatcher = Dispatcher()
    memory_agent = _FakeAgent("memory", AgentCapabilities(declared={AgentCapability.MEMORY}))
    research_agent = _FakeAgent("research", AgentCapabilities(declared={AgentCapability.RESEARCH}))
    task = _task(metadata={"required_capability": AgentCapability.MEMORY})

    result = dispatcher.dispatch(
        Decision(requires_memory=True), task, {"research": research_agent, "memory": memory_agent}
    )

    assert result is memory_agent


def test_dispatch_only_routes_the_task_that_actually_carries_the_capability_tag():
    dispatcher = Dispatcher()
    memory_agent = _FakeAgent("memory", AgentCapabilities(declared={AgentCapability.MEMORY}))
    decision = Decision(requires_memory=True)
    tagged_task = _task(task_id="t1", metadata={"required_capability": AgentCapability.MEMORY})
    untagged_task = _task(task_id="t2")

    assert dispatcher.dispatch(decision, tagged_task, {"memory": memory_agent}) is memory_agent
    assert dispatcher.dispatch(decision, untagged_task, {"memory": memory_agent}) is None


def test_dispatch_honors_an_explicit_selected_agent_override():
    dispatcher = Dispatcher()
    research_agent = _FakeAgent("research", AgentCapabilities(declared={AgentCapability.RESEARCH}))

    result = dispatcher.dispatch(
        Decision(selected_agent="research"), _task(), {"research": research_agent}
    )

    assert result is research_agent


def test_dispatch_selected_agent_override_returns_none_if_name_not_found():
    dispatcher = Dispatcher()

    result = dispatcher.dispatch(Decision(selected_agent="missing"), _task(), {})

    assert result is None


def test_adding_a_new_candidate_agent_requires_no_dispatcher_code_change():
    # Open/Closed: Dispatcher's own code never changes - registering a new
    # agent instance with the right capability is enough for it to start
    # being selected.
    dispatcher = Dispatcher()
    decision = Decision(requires_tools=True)
    task = _task(metadata={"required_capability": AgentCapability.TOOLS})
    candidates = {}

    assert dispatcher.dispatch(decision, task, candidates) is None

    candidates["new-tool-agent"] = _FakeAgent("new-tool-agent", AgentCapabilities(declared={AgentCapability.TOOLS}))

    assert dispatcher.dispatch(decision, task, candidates) is candidates["new-tool-agent"]
