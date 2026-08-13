import pytest

from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.execution import ToolExecutor
from app.services.ai.tools.factory import ToolFactory
from app.services.ai.tools.manager import ToolManager
from app.services.ai.tools.registry import ToolRegistry
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.schema import SchemaField, ToolSchema
from app.services.ai.tools.shared.exceptions import ToolNotFoundError


class _FakeTool(BaseTool):
    def __init__(self, label="default"):
        self.label = label
        self.executed_with: list[ToolContext] = []

    @property
    def tool_id(self) -> str:
        return "fake-tool"

    @property
    def name(self) -> str:
        return "Fake Tool"

    @property
    def description(self) -> str:
        return ""

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CUSTOM_BUSINESS

    @property
    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset()

    @property
    def permissions(self) -> frozenset[ToolPermission]:
        return frozenset()

    def input_schema(self) -> ToolSchema:
        return ToolSchema(fields=(SchemaField(name="query", type="string"),))

    def output_schema(self) -> ToolSchema:
        return ToolSchema()

    def validate(self, parameters) -> None:
        return None

    def execute(self, context: ToolContext) -> ToolResult:
        self.executed_with.append(context)
        return ToolResult(success=True, output=context.parameters.get("query"))

    def health_check(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(ToolRegistry._providers)
    ToolRegistry._providers.clear()
    yield
    ToolRegistry._providers.clear()
    ToolRegistry._providers.update(original)


@pytest.fixture(autouse=True)
def _register_fake_tool():
    ToolRegistry.register("fake-tool", _FakeTool, name="Fake Tool", category=ToolCategory.CUSTOM_BUSINESS)


def test_invoke_resolves_the_tool_via_the_factory_and_returns_a_result():
    manager = ToolManager()

    result = manager.invoke("fake-tool", {"query": "hello"})

    assert result.success is True
    assert result.output == "hello"


def test_invoke_raises_for_an_unregistered_tool():
    manager = ToolManager()

    with pytest.raises(ToolNotFoundError):
        manager.invoke("missing-tool", {})


def test_invoke_forwards_constructor_arguments_to_the_factory():
    manager = ToolManager()

    result = manager.invoke("fake-tool", {"query": "hi"}, tool_kwargs={"label": "custom"})

    assert result.success is True


def test_invoke_propagates_agent_id_and_workflow_id_onto_the_context():
    executed_context = None

    class _CapturingExecutor(ToolExecutor):
        def execute(self, tool, context):
            nonlocal executed_context
            executed_context = context
            return super().execute(tool, context)

    manager = ToolManager(executor=_CapturingExecutor())
    manager.invoke("fake-tool", {"query": "hi"}, agent_id="agent-1", workflow_id="wf-1")

    assert executed_context.agent_id == "agent-1"
    assert executed_context.workflow_id == "wf-1"


def test_invoke_uses_a_provided_shared_execution_context():
    shared = SharedExecutionContext(organization_id=7)
    manager = ToolManager()

    executed_context = None

    class _CapturingExecutor(ToolExecutor):
        def execute(self, tool, context):
            nonlocal executed_context
            executed_context = context
            return super().execute(tool, context)

    manager = ToolManager(executor=_CapturingExecutor())
    manager.invoke("fake-tool", {"query": "hi"}, shared=shared)

    assert executed_context.organization_id == 7


def test_invoke_propagates_execution_depth():
    executed_context = None

    class _CapturingExecutor(ToolExecutor):
        def execute(self, tool, context):
            nonlocal executed_context
            executed_context = context
            return super().execute(tool, context)

    manager = ToolManager(executor=_CapturingExecutor())
    manager.invoke("fake-tool", {"query": "hi"}, execution_depth=3)

    assert executed_context.execution_depth == 3


def test_invoke_propagates_a_cancellation_token():
    token = CancellationToken()
    token.cancel()
    manager = ToolManager()

    result = manager.invoke("fake-tool", {"query": "hi"}, cancellation_token=token)

    assert result.success is False


def test_invoke_uses_an_injected_executor():
    calls = []

    class _RecordingExecutor(ToolExecutor):
        def execute(self, tool, context):
            calls.append((tool.tool_id, dict(context.parameters)))
            return super().execute(tool, context)

    manager = ToolManager(executor=_RecordingExecutor())

    manager.invoke("fake-tool", {"query": "hi"})

    assert calls == [("fake-tool", {"query": "hi"})]


def test_invoke_uses_an_injected_factory():
    class _StubFactory(ToolFactory):
        pass

    manager = ToolManager(factory=_StubFactory)

    result = manager.invoke("fake-tool", {"query": "hi"})

    assert result.success is True


def test_two_managers_do_not_share_executor_state():
    first = ToolManager()
    second = ToolManager()

    assert first.executor is not second.executor
