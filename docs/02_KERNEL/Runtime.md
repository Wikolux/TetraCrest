# Runtime

`app/services/ai/runtime/` is the AI Operating System's **working** execution engine for the Conversation capability — the fully-implemented counterpart to the [Kernel](Kernel.md)'s largely-declared execution model. Every other capability execution engine in this platform (`ToolExecutor`, `VisionExecutor`) mirrors this one's shape almost exactly.

## Public Facade: `AIRuntime`

```python
class AIRuntime:
    def __init__(
        self,
        middleware: tuple[RuntimeMiddleware, ...] = (),
        hooks: tuple[RuntimeHook, ...] = (),
        event_publisher: RuntimeEventPublisher | None = None,
        max_retries: int = 0,
        executor: RuntimeExecutor | None = None,
    ) -> None: ...

    def execute(self, request: RuntimeRequest) -> RuntimeResponse: ...
    async def execute_stream(self, request: RuntimeRequest) -> AsyncIterator[ConversationStreamChunk]: ...
    def health(self) -> dict[ProviderName, bool]: ...
    def capabilities(self) -> dict[ProviderName, ProviderCapabilities]: ...
    def providers(self) -> tuple[ProviderName, ...]: ...
```

`execute()` delegates directly to `RuntimeExecutor.execute()` — all retry/timeout/middleware/event logic lives there. `execute_stream()` is notably **not** routed through the executor: it resolves a provider directly via `ConversationProviderFactory.create(...)` and iterates `provider.stream(...)`, checking `request.cancellation_token.cancelled()` between chunks. This means streaming currently has **no retry, no middleware pipeline, and no event emission** — a real, current asymmetry with the non-streaming path, worth knowing before building on it. `health()`/`capabilities()` construct every registered provider and never let one provider's exception affect another's result.

## Execution Lifecycle

```mermaid
sequenceDiagram
    participant Caller
    participant Exec as RuntimeExecutor
    participant MW as MiddlewarePipeline
    participant Factory as ConversationProviderFactory
    participant Provider

    Caller->>Exec: execute(RuntimeRequest)
    Exec->>Exec: shared = request.parent_shared.child() or SharedExecutionContext()
    Exec->>Exec: build RuntimeContext(shared, provider, model, timeout)
    Exec-->>Caller: emit EventType.STARTED
    Exec->>Exec: before_execution hooks
    alt already cancelled
        Exec-->>Caller: emit CANCELLED; on_cancel/after_execution hooks
    else
        loop attempt in 1..max_retries+1
            Exec->>Exec: re-check cancellation
            Exec->>MW: run(context, request, _handler)
            MW->>Factory: create(request.provider, config)
            alt provider unresolvable
                Factory--xMW: raise AIProviderError
                Note over Exec: not retryable — breaks immediately
            else resolved
                MW->>Provider: RuntimeTimeout(timeout).run(provider.generate, prompt_package)
                Exec-->>Caller: emit PROVIDER_SELECTED, REQUEST_SENT
                alt success
                    Provider-->>MW: ConversationResponse
                    Exec-->>Caller: emit RESPONSE_RECEIVED
                else RuntimeTimeoutError
                    Exec-->>Caller: emit TIMEOUT; on_timeout hook
                else other Exception
                    Exec->>Exec: on_error hook
                end
            end
        end
    end
    Exec-->>Caller: emit COMPLETED or FAILED
    Exec->>Exec: after_execution hooks
    Exec-->>Caller: RuntimeResponse (success/error, identity, latency, events)
```

Every failure path — `AIProviderError`, `RuntimeTimeoutError`, a bare `Exception`, or cancellation — is caught inside `execute()` and converted into `RuntimeResponse(success=False, error=...)`. Nothing propagates out of `execute()` as a raised exception.

## Middleware

`RuntimeMiddleware` (`ABC`, subclasses `shared.middleware.GenericMiddleware`) wraps `__call__(context: RuntimeContext, request: RuntimeRequest, call_next: RuntimeHandler) -> RuntimeExecutionResult`. `MiddlewarePipeline` (subclasses `GenericMiddlewarePipeline`) composes an ordered tuple of middleware from the outside in — the first middleware in the tuple is the outermost, seeing the request first and the result last, exactly like FastAPI/ASGI middleware. No concrete middleware exists yet; only the contract and composition logic. See [Middleware.md](Middleware.md).

## Hooks

`RuntimeHook` is a plain (non-ABC) class with five concrete no-op methods: `before_execution`, `after_execution`, `on_error`, `on_cancel`, `on_timeout`. A caller subclasses it and overrides only what it needs; a bare `RuntimeHook()` is a valid, fully-functional no-op.

## Retry

Controlled by `AIRuntime`/`RuntimeExecutor`'s `max_retries: int` constructor parameter (default `0` — no retries). The retry loop runs `max_retries + 1` total attempts. `AIProviderError` (an unresolvable provider name) is deliberately **not retried** — retrying a name that can't resolve would fail identically every time. `RuntimeTimeoutError` and any other exception **are** retryable by default.

## Timeout

`RuntimeTimeout(seconds: float | None).run(func, *args, **kwargs)` (`runtime/timeout.py`) is **retrospective, not preemptive**: it calls `func` to completion and then raises `RuntimeTimeoutError` if the elapsed wall-clock time exceeded `seconds`. `seconds=None` disables the check entirely. This means a slow provider call is never actually interrupted mid-flight — timeout here is a reporting mechanism, not a cancellation mechanism. Genuine interruption is `CancellationToken`'s job, checked between attempts, not within one.

## Cancellation

`CancellationToken` (`runtime/cancellation.py`) is a deliberately simple, cooperative flag — no threading or asyncio primitives:

```python
class CancellationToken:
    def cancel(self) -> None: ...        # sets an internal flag
    def cancelled(self) -> bool: ...      # reads it
```

`RuntimeExecutor` checks `request.cancellation_token.cancelled()` before starting and again before every retry attempt — never *during* a single provider call in progress. This same token is reused directly (never re-implemented) by `ToolExecutor` and `VisionExecutor`.

## Provider Resolution

`AIRuntime`/`RuntimeExecutor` know only `ConversationProviderFactory`/`ConversationProviderRegistry`/`ProviderName` — never a specific vendor. `RuntimeExecutor`'s constructor accepts `provider_factory: ProviderFactoryCallable = ConversationProviderFactory.create`, injectable for testing.

## Events

`EventType` (StrEnum, `runtime/types.py`): `STARTED`, `PROVIDER_SELECTED`, `REQUEST_SENT`, `RESPONSE_RECEIVED`, `COMPLETED`, `FAILED`, `CANCELLED`, `TIMEOUT`. `RuntimeEvent` subclasses `shared.events.GenericEvent`; `RuntimeEventPublisher` subclasses `shared.events.EventPublisher[RuntimeEvent]`. Full detail: [Event_System.md](Event_System.md).

## Identity Propagation

`RuntimeRequest.parent_shared: SharedExecutionContext | None` lets a caller that already has its own execution context (an Executive's, a Specialist's) propagate it as the parent of a new child execution via `SharedExecutionContext.child()`. This is what makes "Executive → Specialist → Runtime" one execution tree sharing a single `correlation_id`, not three independent ones. `RuntimeResponse`'s `execution_id`/`parent_execution_id`/`correlation_id`/`causation_id` are populated from `context.shared.identity_fields()` at the end of every execution. Full detail: [Execution_Context.md](Execution_Context.md).

## Value Objects

| Type | Purpose |
|---|---|
| `RuntimeContext` | Tracks identity/progress through one execution (composes `SharedExecutionContext`; adds `provider`, `provider_model`, `attempt`, `retry_count`, `timeout`, `runtime_metadata`) |
| `RuntimeRequest` | One request into the Runtime (`organization_id`, `prompt_package`, `provider`, `conversation_id`, `model`, `temperature`, `max_tokens`, `stream`, `timeout`, `cancellation_token`, `parent_shared`, `metadata`) |
| `RuntimeExecutionResult` | Internal, per-attempt outcome (`success`, `conversation_response`, `error`, `attempt`, `duration_ms`, `retryable`) |
| `RuntimeResponse` | The public, whole-execution result — identity fields, `provider`, `conversation_response`, `latency_ms`, `usage`, `events`, `warnings`, `error` |
