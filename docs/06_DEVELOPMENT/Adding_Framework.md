# Adding a Capability Framework

This guide is for adding an entirely new **shared OS capability** — not a new agent, not a new tool, not a new provider for an existing capability, but a new capability altogether, the way Vision was added alongside Conversation in M19. The Roadmap's Audio Framework and Speech Framework are the concrete near-term candidates for this. Use [Vision_Framework.md](../04_CAPABILITIES/Vision_Framework.md) as your primary worked reference — this guide extracts the repeatable steps from how it was actually built.

## When This Applies (and When It Doesn't)

Build a new capability framework when you're adding something agents should be able to *use as a shared platform service*, reachable by any current or future agent, provider-agnostic by construction — the same category as "understand an image" or "generate a conversational response." Do **not** reach for this pattern to add a single agent-specific behavior; that's a [tool](Adding_Tool.md) or a [specialist](Adding_Agent.md) instead.

## Steps

1. **Decide your capability categories.** Vision split into four independent services (image/document/extraction/analysis) because each has a genuinely different primary verb and no shared "analyze"-shaped method made sense across all of them. Your new framework might be one capability or several — decide based on whether the sub-capabilities have real behavioral differences, not just naming variety.

2. **Build the package skeleton**, mirroring Vision's exactly:

```
your_capability/
    shared/          types.py, exceptions.py, base_provider.py
    providers/       enums.py (re-export the platform ProviderName — do not redeclare it)
    capabilities/    enums.py (your capability-category enum + one enum per sub-capability)
    {sub_capability}/    base_provider.py, registry.py, provider_factory.py   (one folder per capability, if more than one)
    runtime.py       YourCapabilityRuntime
    context.py       YourCapabilityContext
    request.py       YourCapabilityRequest, YourCapabilityInput
    response.py       YourCapabilityResponse
    events.py        YourCapabilityEvent, YourCapabilityEventPublisher, YourCapabilityEventType
    hooks.py         YourCapabilityHook
    middleware.py    YourCapabilityMiddleware, YourCapabilityMiddlewarePipeline
    execution.py     YourCapabilityExecutor
```

3. **Compose, don't redefine, shared infrastructure.** Your request/response/context types compose `SharedExecutionContext`; your registries extend `GenericProviderRegistry`; your events subclass `GenericEvent` (remember to restate `__hash__ = hash_event` on every re-decorated subclass); your middleware subclasses `GenericMiddleware`/`GenericMiddlewarePipeline` (remember to re-apply `@abstractmethod`); your provider factories extend `BaseProviderFactory`, constructed from `BaseProviderConfig` unless you have a genuine reason for a capability-specific config type. See [Shared_Infrastructure.md](../01_ARCHITECTURE/Shared_Infrastructure.md).

4. **Build `BaseYourCapabilityProvider` holding only what's genuinely common** across every sub-capability — abstract `health_check`/`provider_name`/`model_name`, concrete-with-safe-defaults `initialize`/`shutdown`/`capabilities`/`metadata`. Deliberately do **not** put a primary verb (like `analyze`) on this base — that belongs on each sub-capability's own ABC, one abstract method each, with a domain-appropriate name.

5. **Structure your request type to support the realistic future, not just today's need.** Vision's `VisionRequest.inputs` is always a tuple, never a single-item field, specifically so multi-item/batch/streaming use cases don't require a breaking change later. If your capability might reasonably batch (multiple audio clips, a multi-page document), do the same from day one.

6. **Build `YourCapabilityExecutor`** mirroring `VisionExecutor`/`RuntimeExecutor`: resolve provider via factory → run through middleware pipeline → wrap the provider call in `RuntimeTimeout` (reused from `runtime/`, never re-implemented) → check `CancellationToken` (reused from `runtime/`) before starting and between retries → catch `AIProviderError` as non-retryable, other exceptions/timeouts as retryable → emit a `*_STARTED` event, capability-specific events, and a `*_COMPLETED`/`*_FAILED` event → always return a structured response, never raise.

7. **Build `YourCapabilityRuntime`** as the sole public entry point — `execute()` delegates to the executor; `health()`/`capabilities()`/`providers()` aggregate across every registered sub-capability registry, never letting one broken provider's exception affect another's result.

8. **Write architecture-only first, provider-second.** Prove the framework provider-agnostic by exercising every layer with hand-written fakes before any real vendor implementation exists — this is what makes the "provider-agnostic by construction" claim verifiable rather than just intended. Aim for the same order of magnitude of test coverage Vision achieved (232 tests) relative to your framework's actual surface area — the number itself isn't the point; covering ABC enforcement, registry Open/Closed compliance, retry/timeout/cancellation, middleware, hooks, events, identity propagation, and determinism is.

9. **Before finalizing, look for unification opportunities with existing frameworks**, exactly as the Vision milestone's own brief required. If you find yourself duplicating a registry, event, or middleware shape a fourth or fifth time, that's the signal to extend the shared generics rather than copy them again — see [ADR-0002](../ADR/ADR-0002.md) for how this reasoning played out for Vision itself.

10. **Update the dependency rules and package architecture docs** ([Dependency_Rules.md](../01_ARCHITECTURE/Dependency_Rules.md), [Package_Architecture.md](../01_ARCHITECTURE/Package_Architecture.md)) as part of the same change — per the "three artifacts" rule (code, tests, docs) this documentation sprint recommends adopting going forward.

## Checklist

- [ ] Package skeleton mirrors Vision's exactly (shared/, providers/, capabilities/, one folder per sub-capability, runtime/context/request/response/events/hooks/middleware/execution at the top level)
- [ ] Zero vendor SDK/HTTP/library imports outside concrete provider modules
- [ ] Request type structurally supports realistic future batching/multi-item use, not just today's single-item case
- [ ] Composes `SharedExecutionContext`, extends `GenericProviderRegistry`/`GenericEvent`/`GenericMiddleware`, reuses `CancellationToken`/`RuntimeTimeout`/`ExecutionMetrics` — nothing platform-level redefined
- [ ] Executor never raises — always returns a structured response
- [ ] Full test suite exercising every layer with hand-written fakes before any real provider exists
- [ ] Reviewed against existing frameworks for unification opportunities before finalizing
- [ ] Dependency_Rules.md and Package_Architecture.md updated in the same change
