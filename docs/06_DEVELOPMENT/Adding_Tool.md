# Adding a Tool

This guide covers adding a new tool to the [Tool Framework](../04_CAPABILITIES/Tool_Framework.md). No concrete tool ships with the platform today — you would be the first, so there is no existing worked example to copy the way [Research_Agent.md](../05_AGENTS/Research_Agent.md) exists for specialists. Follow the framework's own contract carefully.

## Steps

1. **Implement `BaseTool`.**

```python
from app.services.ai.tools.base_tool import BaseTool

class WebSearchTool(BaseTool):
    def execute(self, context: ToolContext, params: dict) -> ToolResult: ...
    # every other BaseTool abstract method
    # manifest() is concrete — inherited, not overridden, unless you need custom manifest logic
```

Write a parametrized "missing any required member cannot be instantiated" test before writing behavior tests, matching the pattern used throughout every ABC in this platform.

2. **Declare your tool's schema.** Use `ToolSchema`/`SchemaField` (`tools/schema.py`) — pure Python, no external validation library. This is what `ToolExecutor` validates incoming `params` against before your tool's `execute()` is ever called.

3. **Decide your tool's category, capabilities, and permissions up front.** These are supplied at *registration time*, not derived from your class:

```python
ToolRegistry.register(
    "web_search",
    WebSearchTool,
    name="Web Search",
    category=ToolCategory.SEARCH,
    capabilities=frozenset({ToolCapability.SEARCH}),
    permissions=frozenset({ToolPermission.NETWORK}),
)
```

Get this right — `ToolRegistry.categories()`/`.capabilities()` (used for discovery) and `PermissionPolicy` checks (used for authorization) both read this metadata without ever instantiating your tool.

4. **Never bypass `ToolExecutor`.** Your tool's `execute()` should assume it's being called *through* `ToolExecutor` — which handles validation, permission checks, middleware, retry, timeout, and cancellation around it — not called directly by an agent. If you find an agent calling `WebSearchTool().execute(...)` directly anywhere, that's a bug: it should go through `ToolAdapter` → `ToolExecutor`.

5. **Respect cancellation.** If your tool's work is long-running or has natural checkpoints, check `context.cancellation_token.cancelled()` at those checkpoints — `ToolContext` always carries one.

6. **Register.**

```python
ToolRegistry.register("web_search", WebSearchTool, name=..., category=..., capabilities=..., permissions=...)
```

No change to `ToolExecutor`, `ToolFactory`, or `ToolManager` should ever be required to add a tool — if you find yourself editing any of those three, stop and reconsider; that's a sign the registry/factory contract isn't being used as intended.

7. **Test.** Follow `test_tool_registry.py`/`test_tool_execution.py`'s patterns: registry registration and Open/Closed compliance (a new tool needs zero factory modification), schema validation (both valid and invalid params), permission enforcement, retry/timeout/cancellation behavior via a hand-written fake provider of varying behavior (success/raises/delay), and event ordering through `ToolEventPublisher`.

## Checklist

- [ ] Implements the full `BaseTool` contract (verified by an ABC-enforcement test)
- [ ] Has a `ToolSchema` describing its expected params
- [ ] Registered with accurate `category`/`capabilities`/`permissions` at registration time, not derived by instantiation
- [ ] Never called directly by an agent — always through `ToolExecutor`/`ToolAdapter`
- [ ] Checks `context.cancellation_token` at natural checkpoints if long-running
- [ ] No modification to `ToolExecutor`, `ToolFactory`, `ToolRegistry`, or `ToolManager`
- [ ] Full test suite: ABC enforcement, schema validation, permission checks, retry/timeout/cancellation, events
