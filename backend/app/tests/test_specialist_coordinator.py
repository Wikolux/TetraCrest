from app.services.ai.agents.specialists.coordinator import SpecialistCoordinator
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.planner import SpecialistPlanner
from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.agents.specialists.tool_adapter import ToolAdapter


class _FakePlanner(SpecialistPlanner):
    def plan(self, context):
        return ()

    def replan(self, context, previous_plan):
        return ()

    def evaluate(self, context, plan):
        return True

    def next_step(self, context, plan):
        return None


def test_coordinator_holds_every_declared_collaborator():
    planner = _FakePlanner()
    memory_adapter = MemoryAdapter(pipeline=object())
    tool_adapter = ToolAdapter(manager=object())
    runtime_adapter = RuntimeAdapter(runtime=object())
    synthesizer = object()

    coordinator = SpecialistCoordinator(
        planner=planner,
        memory_adapter=memory_adapter,
        tool_adapter=tool_adapter,
        runtime_adapter=runtime_adapter,
        synthesizer=synthesizer,
    )

    assert coordinator.planner is planner
    assert coordinator.memory_adapter is memory_adapter
    assert coordinator.tool_adapter is tool_adapter
    assert coordinator.runtime_adapter is runtime_adapter
    assert coordinator.synthesizer is synthesizer


def test_synthesizer_defaults_to_none():
    coordinator = SpecialistCoordinator(
        planner=_FakePlanner(),
        memory_adapter=MemoryAdapter(pipeline=object()),
        tool_adapter=ToolAdapter(manager=object()),
        runtime_adapter=RuntimeAdapter(runtime=object()),
    )

    assert coordinator.synthesizer is None


def test_coordinator_contains_no_business_logic_of_its_own():
    # a plain DI container has no methods beyond what @dataclass generates
    own_methods = [
        name
        for name in vars(SpecialistCoordinator)
        if not name.startswith("__") and callable(getattr(SpecialistCoordinator, name))
    ]

    assert own_methods == []


def test_two_coordinators_do_not_share_state():
    first = SpecialistCoordinator(
        planner=_FakePlanner(),
        memory_adapter=MemoryAdapter(pipeline=object()),
        tool_adapter=ToolAdapter(manager=object()),
        runtime_adapter=RuntimeAdapter(runtime=object()),
    )
    second = SpecialistCoordinator(
        planner=_FakePlanner(),
        memory_adapter=MemoryAdapter(pipeline=object()),
        tool_adapter=ToolAdapter(manager=object()),
        runtime_adapter=RuntimeAdapter(runtime=object()),
    )

    assert first.planner is not second.planner
