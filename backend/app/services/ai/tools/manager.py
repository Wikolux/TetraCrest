"""ToolManager - the single entry point every agent (including the
Executive) uses to invoke a tool. Nothing else: resolve the tool, build
its context, invoke the executor, return the result.
"""

from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.execution import ToolExecutor
from app.services.ai.tools.factory import ToolFactory
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.shared.types import Metadata


class ToolManager:
    def __init__(
        self,
        executor: ToolExecutor | None = None,
        factory: type[ToolFactory] = ToolFactory,
    ) -> None:
        self.executor = executor or ToolExecutor()
        self.factory = factory

    def invoke(
        self,
        tool_id: str,
        parameters: Metadata | None = None,
        *,
        shared: SharedExecutionContext | None = None,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        execution_depth: int = 0,
        cancellation_token: CancellationToken | None = None,
        tool_args: tuple = (),
        tool_kwargs: dict | None = None,
    ) -> ToolResult:
        tool = self.factory.create(tool_id, *tool_args, **(tool_kwargs or {}))
        context = ToolContext(
            tool_id,
            shared,
            agent_id=agent_id,
            workflow_id=workflow_id,
            execution_depth=execution_depth,
            parameters=parameters,
            cancellation_token=cancellation_token,
        )
        return self.executor.execute(tool, context)
