# Philosophy

This document lists the concrete engineering conventions that the [Vision](Vision.md)'s design philosophy actually produces in code. Where `Vision.md` explains *why*, this document explains *what that looks like in every file you'll read in this codebase*. Every rule below is drawn from patterns actually enforced across the implementation (verified via the platform's test suite), not aspirational guidance.

## 1. Immutability by default

Every value object in the AI Operating System — requests, responses, contexts, events, policies, metrics — is a frozen `@dataclass`. Fields that hold a mutable mapping (`dict`) are coerced to `types.MappingProxyType` in `__post_init__`, so a caller can never mutate a request or response after construction, and two independent execution paths handed the same object can't step on each other.

```python
@dataclass(frozen=True)
class SomeRequest:
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
```

A frozen dataclass that holds a `MappingProxyType` field needs a **custom `__hash__`** if it's ever hashed — the auto-generated one tries to hash every field, and `MappingProxyType` is not hashable. This was a real, repeatedly-rediscovered gap (see [ADR-0001](../ADR/ADR-0001.md) and the Event System's `hash_event()`, [Event_System.md](../02_KERNEL/Event_System.md)) before it was solved once, platform-wide.

## 2. Never raise, always return

Every execution engine — `RuntimeExecutor`, `AgentExecutor`, `ToolExecutor`, `VisionExecutor`, `ExecutiveAgent`, `ResearchAgent` — returns a structured result object with a `success: bool` and an `error: str | None`, never an unhandled exception. A provider raising, a timeout firing, cancellation, or an unresolvable provider name are all converted into that same structured shape. This is enforced consistently enough that no execution engine's public `execute()`/`run()` method has a documented exception contract — callers are never expected to wrap a call in `try/except` to stay safe.

## 3. Composition over inheritance for identity

`RuntimeContext`, `AgentContext`, `ToolContext`, `VisionContext`, the Kernel's `ExecutionContext`, and every specialist context **compose** `SharedExecutionContext` (hold it as a `shared` field) rather than each redeclaring `execution_id`/`correlation_id`/etc. themselves. See [Execution_Context.md](../02_KERNEL/Execution_Context.md) and [ADR-0001](../ADR/ADR-0001.md).

## 4. Registries as the only extension point

No framework in this platform dispatches on a hardcoded `if provider_name == "openai": ...` chain. Every capability's provider/tool/agent/specialist is resolved through a class-level registry (`register`/`unregister`/`clear`/`get`/`is_registered`/`all_registered`), guarded by a `threading.RLock`, rejecting duplicate registration unless `overwrite=True` is passed explicitly. As of the M19 completion pass, every such registry is built on one shared base, `GenericProviderRegistry` — see [Shared_Infrastructure.md](../01_ARCHITECTURE/Shared_Infrastructure.md) and [ADR-0002](../ADR/ADR-0002.md).

## 5. Factories resolve, they don't decide

A `*ProviderFactory.create(provider_name, config)` call resolves a class via the corresponding registry and constructs it — it never contains capability logic, never falls back to a default vendor, and raises a single, consistent `AIProviderError` when nothing is registered. This is deliberately a thin, mechanical layer so "add a provider" never means "also update the factory."

## 6. Middleware is FastAPI-shaped, deliberately

Every middleware contract in the platform (`RuntimeMiddleware`, `ToolMiddleware`, `VisionMiddleware`) has the same `__call__(context, subject, call_next)` shape, composed by a pipeline that wraps the innermost handler from the last middleware outward — exactly the ASGI middleware-composition model most engineers already know from FastAPI. This was chosen specifically so the mental model transfers without new vocabulary.

## 7. Hooks observe; middleware transforms

A `*Hook` class (`RuntimeHook`, `ToolHook`, `VisionHook`) is a plain, non-abstract class with concrete no-op methods — a caller overrides only the lifecycle point they care about. Hooks never return a value that changes control flow; that's what middleware is for. This split is deliberate and consistent across every framework.

## 8. Tests are written against fakes, never mocks

No framework test in this platform uses `unittest.mock`. Every test builds a small, hand-written fake (a fake provider, a fake tool, a fake agent) that implements the real abstract contract. This is why ABC-enforcement tests (`test_a_subclass_missing_any_required_member_cannot_be_instantiated`) exist throughout — the fakes double as proof that the contract is enforceable, not just documented.

## 9. Extraction happens after duplication is observed, not before

`GenericProviderRegistry`, `GenericEvent`/`EventPublisher`, and `GenericMiddleware`/`GenericMiddlewarePipeline` were extracted during the Vision milestone (M19) specifically because Vision would have been the *fifth or sixth* hand-copy of the same shape (Conversation, Agent, Tool, Specialist/Executive/Research had each already written one independently). The extraction was then back-applied to the existing five during the M19 completion pass. Compare this to the deliberate decision *not* to extract a generic base for `AgentFactory`/`ToolFactory`/`SpecialistFactory` (three occurrences, but their underlying registries don't yet even agree on method names) or for hooks (same philosophy, but no actual shared logic to lift) — both reviewed and left alone. The rule in practice is: real, growing duplication gets a shared base; superficial shape-similarity without shared logic does not.

## 10. Boundaries are honored even when it costs a few duplicated lines

The Kernel package (`app/services/ai/kernel/`) deliberately imports nothing from elsewhere in `app.services.ai` except one sanctioned line (`ExecutionContext` composing `SharedExecutionContext`). Its own `Metadata`/`Payload` type aliases are declared locally rather than imported from `shared/`, even though `shared/execution_types.Metadata` is identical — because the Kernel's isolation is the point, not an oversight. See [Dependency_Rules.md](../01_ARCHITECTURE/Dependency_Rules.md).
