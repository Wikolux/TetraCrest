import time

from app.services.ai.kernel.retry import RetryPolicy
from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolEventType, ToolPermission
from app.services.ai.tools.events import ToolEventPublisher
from app.services.ai.tools.execution import ToolExecutor
from app.services.ai.tools.hooks import ToolHook
from app.services.ai.tools.middleware import ToolMiddleware
from app.services.ai.tools.permissions import PermissionPolicy
from app.services.ai.tools.policies import ToolExecutionPolicy
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.schema import SchemaField, ToolSchema


class _FakeTool(BaseTool):
    def __init__(self, *, result=None, raises=None, delay=0.0, permissions=(), require_query=False):
        self._result = result if result is not None else ToolResult(success=True, output="ok")
        self._raises = raises
        self._delay = delay
        self._permissions = frozenset(permissions)
        self._require_query = require_query
        self.calls: list[ToolContext] = []

    @property
    def tool_id(self) -> str:
        return "fake-tool"

    @property
    def name(self) -> str:
        return "Fake Tool"

    @property
    def description(self) -> str:
        return "A fake tool."

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
        return self._permissions

    def input_schema(self) -> ToolSchema:
        if self._require_query:
            return ToolSchema(fields=(SchemaField(name="query", type="string"),))
        return ToolSchema()

    def output_schema(self) -> ToolSchema:
        return ToolSchema()

    def validate(self, parameters) -> None:
        return None

    def execute(self, context: ToolContext) -> ToolResult:
        self.calls.append(context)
        if self._delay:
            time.sleep(self._delay)
        if self._raises is not None:
            raise self._raises
        return self._result

    def health_check(self) -> bool:
        return True


class _FlakyTool(_FakeTool):
    def __init__(self, fail_times, **kwargs):
        super().__init__(**kwargs)
        self.fail_times = fail_times
        self.attempts = 0

    def execute(self, context: ToolContext) -> ToolResult:
        self.attempts += 1
        self.calls.append(context)
        if self.attempts <= self.fail_times:
            raise ValueError("transient failure")
        return self._result


class _BadReturnTool(_FakeTool):
    def execute(self, context: ToolContext) -> ToolResult:
        self.calls.append(context)
        return "not a ToolResult"  # type: ignore[return-value]


class _RecordingHook(ToolHook):
    def __init__(self):
        self.calls: list[tuple] = []

    def before_validation(self, context, tool):
        self.calls.append(("before_validation",))

    def after_validation(self, context, tool):
        self.calls.append(("after_validation",))

    def before_execution(self, context, tool):
        self.calls.append(("before_execution",))

    def after_execution(self, context, result):
        self.calls.append(("after_execution", result.success))

    def on_failure(self, context, error):
        self.calls.append(("on_failure", str(error)))

    def on_cancel(self, context):
        self.calls.append(("on_cancel",))


def _event_types(publisher_events):
    return [event.event_type for event in publisher_events]


def _executor_with_events(**kwargs):
    events = []
    publisher = ToolEventPublisher()
    publisher.subscribe(events.append)
    executor = ToolExecutor(event_publisher=publisher, **kwargs)
    return executor, events


# --- successful execution ------------------------------------------------------------


def test_successful_execution_returns_a_success_result():
    tool = _FakeTool()
    executor = ToolExecutor()

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is True
    assert result.output == "ok"
    assert result.error is None


def test_successful_execution_emits_events_in_order():
    tool = _FakeTool()
    executor, events = _executor_with_events()

    executor.execute(tool, ToolContext("fake-tool"))

    assert _event_types(events) == [
        ToolEventType.TOOL_STARTED,
        ToolEventType.VALIDATION_STARTED,
        ToolEventType.VALIDATION_COMPLETED,
        ToolEventType.PERMISSION_GRANTED,
        ToolEventType.EXECUTION_STARTED,
        ToolEventType.EXECUTION_COMPLETED,
    ]


def test_every_event_carries_execution_id_correlation_id_tool_id():
    tool = _FakeTool()
    executor, events = _executor_with_events()
    context = ToolContext("fake-tool", agent_id="agent-1")

    executor.execute(tool, context)

    assert all(event.execution_id == context.execution_id for event in events)
    assert all(event.correlation_id == context.correlation_id for event in events)
    assert all(event.tool_id == "fake-tool" for event in events)
    assert all(event.agent_id == "agent-1" for event in events)


def test_hooks_fire_in_order_for_a_successful_execution():
    hook = _RecordingHook()
    executor = ToolExecutor(hooks=(hook,))

    executor.execute(_FakeTool(), ToolContext("fake-tool"))

    assert hook.calls == [
        ("before_validation",),
        ("after_validation",),
        ("before_execution",),
        ("after_execution", True),
    ]


# --- identity / metrics propagation --------------------------------------------------------


def test_result_identity_is_copied_from_the_context_not_from_events():
    executor = ToolExecutor()
    context = ToolContext("fake-tool")

    result = executor.execute(_FakeTool(), context)

    assert result.execution_id == context.execution_id
    assert result.correlation_id == context.correlation_id
    assert result.parent_execution_id == context.parent_execution_id
    assert result.causation_id == context.causation_id


def test_metrics_are_populated_with_the_contexts_execution_id():
    executor = ToolExecutor()
    context = ToolContext("fake-tool")

    result = executor.execute(_FakeTool(), context)

    assert result.metrics is not None
    assert result.metrics.execution_id == context.execution_id
    assert result.metrics.duration_ms >= 0
    assert result.execution_time_ms == result.metrics.duration_ms


def test_metrics_retry_count_is_zero_on_first_attempt_success():
    executor = ToolExecutor()

    result = executor.execute(_FakeTool(), ToolContext("fake-tool"))

    assert result.metrics.retry_count == 0


# --- input validation ----------------------------------------------------------------------


def test_missing_required_parameter_fails_validation_and_never_executes():
    tool = _FakeTool(require_query=True)
    executor, events = _executor_with_events()

    result = executor.execute(tool, ToolContext("fake-tool", parameters={}))

    assert result.success is False
    assert "query" in result.error
    assert tool.calls == []
    assert ToolEventType.EXECUTION_STARTED not in _event_types(events)
    assert _event_types(events)[-1] == ToolEventType.VALIDATION_COMPLETED


def test_valid_parameters_pass_validation_and_execute():
    tool = _FakeTool(require_query=True)
    executor = ToolExecutor()

    result = executor.execute(tool, ToolContext("fake-tool", parameters={"query": "hi"}))

    assert result.success is True
    assert len(tool.calls) == 1


def test_tools_own_validate_raising_fails_the_execution():
    class _StrictTool(_FakeTool):
        def validate(self, parameters) -> None:
            if not parameters.get("query"):
                raise ValueError("query must not be empty")

    tool = _StrictTool()
    executor = ToolExecutor()

    result = executor.execute(tool, ToolContext("fake-tool", parameters={}))

    assert result.success is False
    assert "query must not be empty" in result.error
    assert tool.calls == []


# --- permission check -----------------------------------------------------------------------


def test_no_policy_configured_allows_execution_regardless_of_required_permissions():
    tool = _FakeTool(permissions=(ToolPermission.NETWORK,))
    executor = ToolExecutor(permission_policy=None)

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is True


def test_missing_permission_denies_execution_and_never_calls_the_tool():
    tool = _FakeTool(permissions=(ToolPermission.NETWORK,))
    executor, events = _executor_with_events(permission_policy=PermissionPolicy())

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is False
    assert "network" in result.error
    assert tool.calls == []
    assert ToolEventType.PERMISSION_DENIED in _event_types(events)
    assert ToolEventType.EXECUTION_STARTED not in _event_types(events)


def test_granted_permission_allows_execution():
    tool = _FakeTool(permissions=(ToolPermission.NETWORK,))
    policy = PermissionPolicy(granted_permissions={ToolPermission.NETWORK})
    executor, events = _executor_with_events(permission_policy=policy)

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is True
    assert ToolEventType.PERMISSION_GRANTED in _event_types(events)


# --- execution failure handling --------------------------------------------------------------


def test_tool_execute_raising_produces_a_failed_result_not_a_raised_exception():
    tool = _FakeTool(raises=ValueError("tool exploded"))
    executor = ToolExecutor()

    result = executor.execute(tool, ToolContext("fake-tool"))  # must not raise

    assert result.success is False
    assert "tool exploded" in result.error


def test_on_failure_hook_fires_when_the_tool_raises():
    hook = _RecordingHook()
    tool = _FakeTool(raises=ValueError("boom"))
    executor = ToolExecutor(hooks=(hook,))

    executor.execute(tool, ToolContext("fake-tool"))

    assert any(call[0] == "on_failure" for call in hook.calls)


def test_execution_failed_event_is_emitted_on_failure():
    executor, events = _executor_with_events()

    executor.execute(_FakeTool(raises=ValueError("boom")), ToolContext("fake-tool"))

    assert ToolEventType.EXECUTION_FAILED in _event_types(events)
    assert ToolEventType.EXECUTION_COMPLETED not in _event_types(events)


def test_a_tool_that_does_not_return_a_tool_result_is_reported_as_a_failure():
    tool = _BadReturnTool()
    executor = ToolExecutor()

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is False
    assert "ToolResult" in result.error


# --- retry integration -----------------------------------------------------------------------


def test_default_retry_policy_retries_up_to_max_attempts():
    tool = _FlakyTool(fail_times=2)
    executor = ToolExecutor(execution_policy=ToolExecutionPolicy(retry_policy=RetryPolicy(max_attempts=3)))

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is True
    assert tool.attempts == 3
    assert result.metrics.retry_count == 2


def test_retries_exhausted_reports_failure():
    tool = _FlakyTool(fail_times=5)
    executor = ToolExecutor(execution_policy=ToolExecutionPolicy(retry_policy=RetryPolicy(max_attempts=2)))

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is False
    assert tool.attempts == 2
    assert "transient failure" in result.error


def test_single_attempt_policy_never_retries():
    tool = _FlakyTool(fail_times=1)
    executor = ToolExecutor(execution_policy=ToolExecutionPolicy(retry_policy=RetryPolicy(max_attempts=1)))

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is False
    assert tool.attempts == 1


# --- timeout ----------------------------------------------------------------------------------


def test_timeout_produces_a_failed_result():
    tool = _FakeTool(delay=0.05)
    executor = ToolExecutor(execution_policy=ToolExecutionPolicy(timeout_seconds=0.01))

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is False


def test_no_timeout_configured_never_fails_a_fast_tool():
    tool = _FakeTool(delay=0.01)
    executor = ToolExecutor(execution_policy=ToolExecutionPolicy(timeout_seconds=None))

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is True


# --- cancellation ------------------------------------------------------------------------------


def test_cancellation_before_start_prevents_any_execution():
    token = CancellationToken()
    token.cancel()
    tool = _FakeTool()
    executor, events = _executor_with_events()

    result = executor.execute(tool, ToolContext("fake-tool", cancellation_token=token))

    assert result.success is False
    assert "cancelled" in result.error.lower()
    assert tool.calls == []
    assert ToolEventType.TOOL_CANCELLED in _event_types(events)


def test_on_cancel_hook_fires_when_cancelled_before_start():
    hook = _RecordingHook()
    token = CancellationToken()
    token.cancel()
    executor = ToolExecutor(hooks=(hook,))

    executor.execute(_FakeTool(), ToolContext("fake-tool", cancellation_token=token))

    assert ("on_cancel",) in hook.calls


def test_cancellation_is_checked_between_retry_attempts():
    token = CancellationToken()

    class _CancelingTool(_FakeTool):
        def execute(self, context):
            self.calls.append(context)
            token.cancel()
            raise ValueError("boom")

    tool = _CancelingTool()
    executor = ToolExecutor(execution_policy=ToolExecutionPolicy(retry_policy=RetryPolicy(max_attempts=3)))

    result = executor.execute(tool, ToolContext("fake-tool", cancellation_token=token))

    assert len(tool.calls) == 1
    assert result.success is False


# --- execution depth policy ------------------------------------------------------------------


def test_execution_beyond_maximum_depth_fails_before_any_validation():
    tool = _FakeTool()
    executor, events = _executor_with_events(execution_policy=ToolExecutionPolicy(maximum_depth=1))

    result = executor.execute(tool, ToolContext("fake-tool", execution_depth=1))

    assert result.success is False
    assert "depth" in result.error.lower()
    assert tool.calls == []
    assert events == []


def test_execution_within_maximum_depth_proceeds_normally():
    tool = _FakeTool()
    executor = ToolExecutor(execution_policy=ToolExecutionPolicy(maximum_depth=5))

    result = executor.execute(tool, ToolContext("fake-tool", execution_depth=2))

    assert result.success is True


# --- middleware integration ------------------------------------------------------------------


def test_middleware_wraps_the_tool_invocation():
    log = []

    class _LoggingMiddleware(ToolMiddleware):
        def __call__(self, context, tool, call_next):
            log.append("before")
            result = call_next(context, tool)
            log.append("after")
            return result

    executor = ToolExecutor(middleware=(_LoggingMiddleware(),))

    executor.execute(_FakeTool(), ToolContext("fake-tool"))

    assert log == ["before", "after"]


def test_middleware_can_short_circuit_and_skip_the_tool():
    class _BlockingMiddleware(ToolMiddleware):
        def __call__(self, context, tool, call_next):
            return ToolResult(success=False, error="blocked by middleware")

    tool = _FakeTool()
    executor = ToolExecutor(middleware=(_BlockingMiddleware(),))

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert result.success is False
    assert result.error == "blocked by middleware"
    assert tool.calls == []


# --- determinism / no mutation ----------------------------------------------------------------


def test_execution_does_not_mutate_the_context():
    tool = _FakeTool()
    executor = ToolExecutor()
    context = ToolContext("fake-tool", parameters={"a": 1})

    executor.execute(tool, context)

    assert dict(context.parameters) == {"a": 1}


def test_structured_output_and_artifacts_pass_through_unchanged():
    expected = ToolResult(success=True, structured_output={"count": 5}, artifacts=("file.txt",))
    tool = _FakeTool(result=expected)
    executor = ToolExecutor()

    result = executor.execute(tool, ToolContext("fake-tool"))

    assert dict(result.structured_output) == {"count": 5}
    assert result.artifacts == ("file.txt",)
