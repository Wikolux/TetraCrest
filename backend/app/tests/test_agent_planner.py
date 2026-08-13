import pytest

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.planner import AgentPlanner

_ALL_METHODS = ("plan", "replan", "evaluate", "next_step")


def test_agent_planner_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        AgentPlanner()


def _stub(name):
    if name == "plan":
        return lambda self, context: ["step-1"]
    if name == "replan":
        return lambda self, context, previous_plan: ["step-1", "step-2"]
    if name == "evaluate":
        return lambda self, context, plan: True
    return lambda self, context, plan: plan[0]


@pytest.mark.parametrize("missing_method", _ALL_METHODS)
def test_a_subclass_missing_any_one_method_cannot_be_instantiated(missing_method):
    namespace = {name: _stub(name) for name in _ALL_METHODS if name != missing_method}
    incomplete = type("IncompletePlanner", (AgentPlanner,), namespace)

    with pytest.raises(TypeError):
        incomplete()


def test_a_subclass_implementing_every_method_can_be_instantiated():
    namespace = {name: _stub(name) for name in _ALL_METHODS}
    complete = type("CompletePlanner", (AgentPlanner,), namespace)
    planner = complete()
    context = AgentContext()

    plan = planner.plan(context)

    assert plan == ["step-1"]
    assert planner.replan(context, plan) == ["step-1", "step-2"]
    assert planner.evaluate(context, plan) is True
    assert planner.next_step(context, plan) == "step-1"
