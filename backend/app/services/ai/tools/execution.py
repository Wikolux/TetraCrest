"""ToolExecutor - owns the full execution lifecycle for one tool
invocation: validation, permission check, the middleware chain, timeout
wrapping, retry orchestration, event emission, and hook execution.

Reuses Kernel/Runtime interfaces directly rather than duplicating them:
RuntimeTimeout (app.services.ai.runtime.timeout) wraps the tool call,
RetryPolicy (app.services.ai.kernel.retry, via ToolExecutionPolicy) drives
retry orchestration, ExecutionMetrics (app.services.ai.kernel.metrics) is
the metrics shape, and CancellationToken (app.services.ai.runtime.cancellation,
held on ToolContext) is checked cooperatively. Always returns a ToolResult;
a validation/permission/execution/timeout/cancellation failure is reported
there via success=False/error, never raised, matching how every other
execution engine in this platform behaves.
"""

import dataclasses
import time

from app.services.ai.kernel.metrics import ExecutionMetrics
from app.services.ai.runtime.timeout import RuntimeTimeout, RuntimeTimeoutError
from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolEventType
from app.services.ai.tools.events import ToolEvent, ToolEventPublisher
from app.services.ai.tools.hooks import ToolHook
from app.services.ai.tools.middleware import ToolMiddleware, ToolMiddlewarePipeline
from app.services.ai.tools.permissions import PermissionPolicy, missing_permissions
from app.services.ai.tools.policies import ToolExecutionPolicy
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.shared.exceptions import ToolExecutionError
from app.services.ai.tools.validation import ExecutionPolicyValidator, InputValidator

_MS_PER_SECOND = 1000


class ToolExecutor:
    def __init__(
        self,
        middleware: tuple[ToolMiddleware, ...] = (),
        hooks: tuple[ToolHook, ...] = (),
        event_publisher: ToolEventPublisher | None = None,
        permission_policy: PermissionPolicy | None = None,
        execution_policy: ToolExecutionPolicy | None = None,
    ) -> None:
        self.middleware_pipeline = ToolMiddlewarePipeline(middleware=middleware)
        self.hooks = hooks
        self.event_publisher = event_publisher or ToolEventPublisher()
        self.permission_policy = permission_policy
        self.execution_policy = execution_policy or ToolExecutionPolicy()

    def execute(self, tool: BaseTool, context: ToolContext) -> ToolResult:
        start = time.monotonic()

        policy_check = ExecutionPolicyValidator.validate(context, self.execution_policy)
        if not policy_check.valid:
            return self._finalize(context, ToolResult(success=False, error="; ".join(policy_check.errors)), start, 0)

        if self._is_cancelled(context):
            return self._cancelled(context, tool, start)

        self._emit(context, tool, ToolEventType.TOOL_STARTED)

        validation_error = self._validate(tool, context)
        if validation_error is not None:
            return self._finalize(context, ToolResult(success=False, error=validation_error), start, 0)

        permission_error = self._check_permissions(tool, context)
        if permission_error is not None:
            return self._finalize(context, ToolResult(success=False, error=permission_error), start, 0)

        self._call_hooks("before_execution", context, tool)
        self._emit(context, tool, ToolEventType.EXECUTION_STARTED)

        result = None
        attempt = 0
        for attempt in range(1, self.execution_policy.retry_policy.max_attempts + 1):
            if self._is_cancelled(context):
                return self._cancelled(context, tool, start)
            result = self._attempt(tool, context)
            if result.success:
                break
            self._call_hooks("on_failure", context, RuntimeError(result.error or "Tool execution failed"))

        if result.success:
            self._emit(context, tool, ToolEventType.EXECUTION_COMPLETED)
        else:
            self._emit(context, tool, ToolEventType.EXECUTION_FAILED, error=result.error)

        final = self._finalize(context, result, start, attempt - 1)
        self._call_hooks("after_execution", context, final)
        return final

    def _validate(self, tool: BaseTool, context: ToolContext) -> str | None:
        self._call_hooks("before_validation", context, tool)
        self._emit(context, tool, ToolEventType.VALIDATION_STARTED)

        schema_result = InputValidator.validate(tool, context.parameters)
        error = "; ".join(schema_result.errors) if not schema_result.valid else None
        if error is None:
            try:
                tool.validate(context.parameters)
            except Exception as exc:  # noqa: BLE001 - a tool's own validate() must never crash the executor
                error = str(exc)

        self._call_hooks("after_validation", context, tool)
        self._emit(context, tool, ToolEventType.VALIDATION_COMPLETED, valid=error is None)
        return error

    def _check_permissions(self, tool: BaseTool, context: ToolContext) -> str | None:
        if self.permission_policy is None:
            self._emit(context, tool, ToolEventType.PERMISSION_GRANTED)
            return None
        missing = missing_permissions(tool, self.permission_policy)
        if missing:
            error = f"Missing permissions: {sorted(p.value for p in missing)}"
            self._emit(context, tool, ToolEventType.PERMISSION_DENIED, missing=sorted(p.value for p in missing))
            return error
        self._emit(context, tool, ToolEventType.PERMISSION_GRANTED)
        return None

    def _attempt(self, tool: BaseTool, context: ToolContext) -> ToolResult:
        def _handler(ctx: ToolContext, t: BaseTool) -> ToolResult:
            raw = RuntimeTimeout(self.execution_policy.timeout_seconds).run(t.execute, ctx)
            if not isinstance(raw, ToolResult):
                raise ToolExecutionError(f"{t.tool_id}.execute() must return a ToolResult, got {type(raw).__name__}")
            return raw

        try:
            return self.middleware_pipeline.run(context, tool, _handler)
        except RuntimeTimeoutError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001 - a tool failure must never escape as a raw exception
            return ToolResult(success=False, error=str(exc))

    def _cancelled(self, context: ToolContext, tool: BaseTool, start: float) -> ToolResult:
        self._emit(context, tool, ToolEventType.TOOL_CANCELLED)
        self._call_hooks("on_cancel", context)
        return self._finalize(context, ToolResult(success=False, error="Execution was cancelled"), start, 0)

    def _finalize(self, context: ToolContext, result: ToolResult, start: float, retry_count: int) -> ToolResult:
        duration_ms = (time.monotonic() - start) * _MS_PER_SECOND
        metrics = ExecutionMetrics(
            duration_ms=duration_ms,
            retry_count=retry_count,
            execution_id=context.execution_id,
        )
        return dataclasses.replace(
            result,
            metrics=metrics,
            execution_time_ms=duration_ms,
            **context.shared.identity_fields(),
        )

    @staticmethod
    def _is_cancelled(context: ToolContext) -> bool:
        return context.cancellation_token is not None and context.cancellation_token.cancelled()

    def _emit(self, context: ToolContext, tool: BaseTool, event_type: ToolEventType, **data) -> None:
        event = ToolEvent(
            event_type=event_type,
            execution_id=context.execution_id,
            correlation_id=context.correlation_id,
            tool_id=tool.tool_id,
            agent_id=context.agent_id,
            data=data,
        )
        self.event_publisher.publish(event)

    def _call_hooks(self, method_name: str, *args) -> None:
        for hook in self.hooks:
            getattr(hook, method_name)(*args)
