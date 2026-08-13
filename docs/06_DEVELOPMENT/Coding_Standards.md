# Coding Standards

These are the conventions actually enforced across `app/services/ai/`, extracted from the implementation rather than aspirational. Follow these when extending any framework in this platform — a pull request that doesn't match them will look inconsistent with everything around it. See [Philosophy.md](../00_OVERVIEW/Philosophy.md) for the reasoning behind each.

## Value Objects

- Every request/response/context/event/policy/metrics type is a **frozen** `@dataclass`.
- Any field holding a mutable mapping is typed `Metadata` (`Mapping[str, Any]`) and coerced to `types.MappingProxyType` in `__post_init__`:

```python
def __post_init__(self) -> None:
    if not isinstance(self.metadata, MappingProxyType):
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
```

- Ordered collections are **tuples**, never lists (`inputs: tuple[VisionInput, ...]`, `events: tuple[RuntimeEvent, ...]`).
- Closed taxonomies are `StrEnum`, not plain `Enum` or string literals.
- If a frozen dataclass holds a `MappingProxyType` field and will ever be hashed, it needs a **custom `__hash__`** based on a stable, unique field alone (never the mapping). For events, use the shared `hash_event()` — see [Event_System.md](../02_KERNEL/Event_System.md). Do not write a new one-off hashing scheme.
- If a subclass adds fields or narrows a parent field's type (common for `event_type`), it must be re-decorated with `@dataclass`, and if the parent had a custom `__hash__`, the subclass must **explicitly restate it** (`__hash__ = hash_event`) — it does not survive re-decoration implicitly.

## Registries

- Class-level state, one `dict` + one `threading.RLock` per registry.
- `register()` rejects a duplicate key unless `overwrite=True` is passed explicitly.
- `unregister()`/`clear()` never raise for an absent key.
- `all_registered()`/`all_registrations()` return a **copy** — never a live view a caller could mutate.
- New registries extend `GenericProviderRegistry[TKey, TValue]` (`app.services.ai.shared.provider_registry`), setting `_registration_error` to the domain's own exception type. Do not hand-roll a new registry from scratch — see [ADR-0002](../ADR/ADR-0002.md).
- If a registry needs extra registration-time metadata beyond a bare class (category, permissions, specialization), wrap it in a small `Registration` dataclass as `TValue` (see `ToolRegistration`, `SpecialistRegistration`) rather than trying to derive that metadata by instantiating the registered class.

## Factories

- A `*Factory.create(...)` resolves via the corresponding registry and constructs — nothing else. No fallback vendor, no capability logic.
- If the domain has exactly one config shape across all its providers (as Conversation and Vision do), extend `BaseProviderFactory[TProvider, TConfig]` and call `BaseProviderFactory.build(...)`.
- If constructor needs are genuinely per-implementation (as Agents/Tools/Specialists are), `create()` forwards `*args/**kwargs` instead — don't force a single config type where none fits.

## Middleware

- `__call__(self, context, subject, call_next)` — always this exact three-argument shape.
- Extend `GenericMiddleware`, and **re-apply `@abstractmethod`** to your narrowed `__call__` override — Python does not treat it as still-abstract otherwise (a subtlety that has caused a real bug before; see [Middleware.md](../02_KERNEL/Middleware.md)).
- Verify with a direct smoke test that your bare middleware class still raises `TypeError` on instantiation before writing the full test suite around it.

## Hooks

- A plain, non-ABC class with concrete no-op methods for every lifecycle point. A bare instance must be a valid, fully-functional no-op.
- Hooks observe; they never return a value that changes control flow. If you need to change the request/response, that's middleware's job, not a hook's.

## Execution Engines

- Every `execute()`/`run()` **returns** a structured result with `success: bool`/`error: str | None` — it never raises for a provider failure, a timeout, or cancellation. If you find yourself writing `try/except` around a call into this platform to stay safe, something upstream isn't following this rule.
- Retry distinguishes retryable failures (a provider call that raised, a timeout) from non-retryable ones (an unresolvable provider name, `AIProviderError`) — don't retry the latter.
- Timeout in this platform is retrospective (`RuntimeTimeout.run()` completes the call, then raises if it took too long), not preemptive. Don't assume a timeout actually interrupts a hung call.
- Cancellation is a cooperative flag (`CancellationToken`), checked between attempts/steps — not a forced interrupt mid-call.
- Build the final result via `**context.shared.identity_fields()` (or the equivalent) rather than manually assigning `execution_id`/`parent_execution_id`/`correlation_id`/`causation_id` one by one.

## Dependency Discipline

- Check [Dependency_Rules.md](../01_ARCHITECTURE/Dependency_Rules.md) before adding a new import across package boundaries. In particular: never import a vendor SDK, HTTP client, or vendor-specific type outside a concrete provider implementation module.
- The Kernel imports nothing outside itself except one sanctioned `SharedExecutionContext` import in `context.py`. Do not add a second exception without a very good, explicitly-argued reason.

## Testing

- No `unittest.mock` — write a small, hand-written fake implementing the real ABC. See [Testing.md](Testing.md).
- Every ABC needs a parametrized "missing any required member cannot be instantiated" test.
- Every registry needs an isolation fixture (snapshot/clear/restore `_providers` around each test) and an Open/Closed test proving a new entry requires no factory/registry code change.

## Don't

- Don't extract a shared abstraction after only one or two real occurrences if the occurrences don't actually share logic (see the hooks/small-policy-object discussion in [Philosophy.md](../00_OVERVIEW/Philosophy.md)) — this is not a hard numeric rule, it's a judgment call about whether there's real duplicated *logic*, not just superficial shape similarity.
- Don't add a vendor-specific field, method, or import to a framework-level type (`ConversationResponse`, `VisionResponse`, `ToolResult`) — those must stay generic across every current and future provider.
- Don't build a placeholder implementation that pretends to do something it doesn't (e.g. a `stream` flag with fake streaming behavior) — an inert, honestly-labeled placeholder (like `VisionRequest.stream`) is fine; a fake one is not.
