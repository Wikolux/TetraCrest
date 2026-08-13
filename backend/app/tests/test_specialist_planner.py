import pytest

from app.services.ai.agents.planner import AgentPlanner
from app.services.ai.agents.specialists.planner import SpecialistPlanner


def test_specialist_planner_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        SpecialistPlanner()


def test_specialist_planner_is_an_agent_planner():
    assert issubclass(SpecialistPlanner, AgentPlanner)


def test_a_complete_subclass_can_be_instantiated():
    class _FakePlanner(SpecialistPlanner):
        def plan(self, context):
            return ()

        def replan(self, context, previous_plan):
            return ()

        def evaluate(self, context, plan):
            return True

        def next_step(self, context, plan):
            return None

    planner = _FakePlanner()

    assert isinstance(planner, SpecialistPlanner)
    assert isinstance(planner, AgentPlanner)
