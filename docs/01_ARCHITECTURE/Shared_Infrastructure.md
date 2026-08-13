# Shared Infrastructure

`app/services/ai/shared/` is the one package every other AI Operating System package is allowed to depend on (see [Dependency_Rules.md](Dependency_Rules.md)). This document explains why each primitive exists, its exact contract, and who uses it today.

## Why This Package Exists

Before the Vision milestone (M19), five subsystems — Conversation, Runtime, Agent, Tool, and (Executive/Research within) the Agent Framework — had each independently written their own registry, their own event type + publisher, and (Runtime and Tools) their own middleware pipeline. They were not different by necessity; they were different because each was written before anyone needed a sixth or seventh copy of the same shape. Vision would have been the fifth or sixth hand-copy. Instead, three generic primitives were extracted, Vision was built directly on them, and — in the M19 completion pass — the five pre-existing subsystems were migrated onto the same generics with zero change to their public APIs or behavior. See [ADR-0001](../ADR/ADR-0001.md) and [ADR-0002](../ADR/ADR-0002.md) for the full reasoning.

## `SharedExecutionContext`

**File**: `shared/execution_context.py`

The single execution identity every subsystem composes rather than redefining. Full detail in [Execution_Context.md](../02_KERNEL/Execution_Context.md) and [Identity_Model.md](../02_KERNEL/Identity_Model.md); summarized here:

```python
@dataclass(frozen=True)
class SharedExecutionContext:
    execution_id: str            # this execution's own identity
    parent_execution_id: str | None
    correlation_id: str | None   # defaults to execution_id if not given
    causation_id: str | None
    session_id: str | None
    request_id: str
    organization_id: int | None
    user_id: int | None
    conversation_id: int | None
    created_at: datetime
    metadata: Metadata

    def child(self, **overrides) -> "SharedExecutionContext": ...
    def identity_fields(self) -> dict[str, str | None]: ...
```

**Who uses it**: `RuntimeContext`, `AgentContext`, `ToolContext`, `VisionContext`, the Kernel's `ExecutionContext`, and every specialist context — all hold one as a `shared` field and expose delegating properties (`context.execution_id` → `self.shared.execution_id`) for backward-compatible flat access.

## `GenericProviderRegistry[TKey, TValue]`

**File**: `shared/provider_registry.py`

```python
class GenericProviderRegistry(Generic[TKey, TValue]):
    _registration_error: type[Exception] = ValueError   # override per subclass

    @classmethod
    def register(cls, key, value, *, overwrite=False) -> None: ...
    @classmethod
    def unregister(cls, key) -> None: ...
    @classmethod
    def clear(cls) -> None: ...
    @classmethod
    def get(cls, key) -> TValue | None: ...
    @classmethod
    def is_registered(cls, key) -> bool: ...
    @classmethod
    def all_registered(cls) -> dict: ...
```

`__init_subclass__` gives every subclass its own independent `_providers` dict and `threading.RLock` — without it, every subclass would share the base class's single dict. `_registration_error` is a class-level override point: each domain registry sets it to its own duplicate-registration exception (`AIProviderError` for Conversation; `AgentError` for Agent and Specialist; `ToolError` for Tool; `VisionProviderError` per Vision capability).

**Who uses it**: `ConversationProviderRegistry`, `AgentRegistry`, `SpecialistRegistry`, `ToolRegistry`, all four Vision capability registries (`ImageVisionProviderRegistry`, `DocumentVisionProviderRegistry`, `ExtractionProviderRegistry`, `AnalysisProviderRegistry`) since the M19 completion pass; and, since M20.5, `app.services.embedding.registry.EmbeddingProviderRegistry` and `app.services.vector_store.registry.VectorStoreRegistry` — both outside `app/services/ai/` entirely, the first consumers of this base from beyond the AI Operating System's own package tree. `ToolRegistry` and `SpecialistRegistry` subclass it with `TValue` set to a small `Registration` dataclass (`ToolRegistration`, `SpecialistRegistration`) carrying extra registration-time metadata (category/capabilities/permissions; specialization/supported_tasks), and override `register()`/`get()` to wrap/unwrap that record — this is the "registration-time metadata over instance introspection" pattern (see [Adding_Tool.md](../06_DEVELOPMENT/Adding_Tool.md)). `EmbeddingProviderRegistry`/`VectorStoreRegistry` instead store a builder *callable* (`Callable[[Settings], Provider]`) as `TValue` — each provider needs several distinct `Settings` fields at construction time, not one uniform config object, so a callable is the natural fit rather than a bare class.

**Not migrated**: `kernel.registry.RuntimeRegistry` is a different concept entirely — instance-level (not class-level) state holding one `KernelRuntime`'s middleware/hooks/capability-runtimes, deliberately never global.

## `GenericEvent` / `EventPublisher[TEvent]`

**File**: `shared/events.py`

```python
@dataclass(frozen=True, kw_only=True)
class GenericEvent:
    event_type: Any
    execution_id: str
    correlation_id: str | None = None   # defaults to execution_id
    timestamp: float
    data: Metadata

    __hash__ = hash_event

class EventPublisher(Generic[TEvent]):
    def subscribe(self, callback) -> None: ...
    def unsubscribe(self, callback) -> None: ...
    def publish(self, event: TEvent) -> None: ...
    def subscriber_count(self) -> int: ...
```

`kw_only=True` is deliberate: every event across the platform is already constructed with keyword arguments only, and `kw_only` is what lets a subclass add a *required* field (e.g. `ToolEvent.tool_id`) after this base's already-defaulted fields (`timestamp`, `data`) without violating dataclass field-ordering rules.

**`hash_event()`** is the one hashing strategy every event type shares: `hash((event.execution_id, event.event_type, event.timestamp))` — never `data`, since `data` is a `MappingProxyType` and unhashable. Full story in [Event_System.md](../02_KERNEL/Event_System.md) and [ADR-0001](../ADR/ADR-0001.md). Every concrete event subclass must explicitly restate `__hash__ = hash_event` in its own class body — a subtlety of dataclass inheritance (a custom `__hash__` does not survive re-decoration with `@dataclass` unless restated).

**Who uses it**: `RuntimeEvent`, `AgentEvent`, `ExecutiveEvent`, `ToolEvent`, `ResearchEvent`, `VisionEvent` all subclass `GenericEvent`; their publishers all subclass `EventPublisher[TEvent]`.

## `GenericMiddleware` / `GenericMiddlewarePipeline`

**File**: `shared/middleware.py`

```python
class GenericMiddleware(ABC):
    @abstractmethod
    def __call__(self, context: Any, subject: Any, call_next: GenericHandler) -> Any: ...

@dataclass(frozen=True)
class GenericMiddlewarePipeline:
    middleware: tuple = field(default_factory=tuple)

    def run(self, context, subject, handler) -> Any:
        # composes middleware from the outside in, exactly like FastAPI/ASGI middleware
        ...
```

**Who uses it**: `RuntimeMiddleware`/`MiddlewarePipeline`, `ToolMiddleware`/`ToolMiddlewarePipeline`, `VisionMiddleware`/`VisionMiddlewarePipeline`. Each concrete `*Middleware` re-declares `__call__` as `@abstractmethod` with its own typed signature (e.g. `(RuntimeContext, RuntimeRequest, RuntimeHandler) -> RuntimeExecutionResult`) — Python does not consider an abstract method "inherited as abstract" once any concrete override appears in the MRO, so this re-declaration is required, not decorative.

**Not migrated**: `kernel.middleware.KernelMiddleware` has a genuinely different shape (`before_execute`/`after_execute`/`on_error`, not an onion `__call__`) — it is not a duplicate of `GenericMiddleware` and was correctly left alone.

## `RetryPolicy`

**File**: `kernel/retry.py` (not `shared/` — see below)

```python
@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    backoff_strategy: BackoffStrategy
    base_delay_ms: float
    max_delay_ms: float
    retry_on: tuple[type[Exception], ...]
```

A pure value object — nothing in the Kernel enforces it; each execution engine (`ToolExecutionPolicy.retry_policy`, `SpecialistExecutionPolicy.retry_policy`) reads it and decides. Reused directly, never redefined, by `agents/policies.py`, `tools/policies.py`, `agents/specialists/shared/policies.py` — each explicitly re-exports it (`from app.services.ai.kernel.retry import RetryPolicy`) rather than declaring a near-identical copy.

## `ExecutionMetrics`

**File**: `kernel/metrics.py`

Generic, provider-independent execution metrics (duration, retry count, execution identity). Composed directly by `VisionResponse.metrics`, and the shape every execution engine's final result is expected to carry duration/retry information in.

## `BaseProviderFactory[TProvider, TConfig]` / `BaseProviderConfig`

**Files**: `shared/base_factory.py`, `shared/provider_config.py`

```python
class BaseProviderFactory(Generic[TProvider, TConfig]):
    @staticmethod
    def build(provider_class, provider_name, config: TConfig, capability_label: str) -> TProvider:
        if provider_class is None:
            raise AIProviderError(f"Unsupported {capability_label} provider: {provider_name}")
        return provider_class(config)
```

The one place "resolve a provider class, fail clearly if none is registered, construct with a config object" is implemented. `ConversationProviderFactory` and all four Vision capability factories call `BaseProviderFactory.build(...)` rather than re-deriving this. `BaseProviderConfig` (api_key/base_url/timeout/max_retries/headers/metadata) is generic enough that Vision's four factories construct providers from it directly — no Vision-specific config type exists.

**Not used by**: `AgentFactory`/`ToolFactory`/`SpecialistFactory`, whose `create()` deliberately forwards `*args/**kwargs` rather than one typed config object — an agent's or tool's constructor needs are genuinely specific to it, unlike a `ConversationProvider`, which is always built from exactly one `ConversationProviderConfig`. See [Package_Architecture.md](Package_Architecture.md) for the full reasoning on why these three factories were reviewed and deliberately not forced onto `BaseProviderFactory`.

## Identity Fields Convention

`identity_fields()` (on `SharedExecutionContext`) returns exactly the four fields every execution artifact copies onto itself:

```python
{"execution_id": ..., "parent_execution_id": ..., "correlation_id": ..., "causation_id": ...}
```

`RuntimeExecutor`, `AgentExecutor`, `ToolExecutor`, and `VisionExecutor` all build their final result via `dataclasses.replace(result, **context.shared.identity_fields())` (or the equivalent direct construction) — the mapping from context to result identity is defined in exactly one place.
