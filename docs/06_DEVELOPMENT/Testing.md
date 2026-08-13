# Testing Standards

Every framework in the AI Operating System was built with its test suite as a co-deliverable, not an afterthought — this document extracts the actual, consistently-applied testing conventions so new work matches them.

## No Mocks — Hand-Written Fakes Only

No test anywhere in `app/services/ai/` uses `unittest.mock`. Instead, tests build small, purpose-built fakes implementing the real abstract contract:

```python
class _FakeProvider:
    def __init__(self, *, result=None, raises=None, delay=0.0):
        self.result = result or VisionResponse(success=True)
        self.raises = raises
        self.delay = delay
        self.calls = []

    def describe(self, request):
        self.calls.append(request)
        if self.delay:
            time.sleep(self.delay)
        if self.raises is not None:
            raise self.raises
        return self.result
```

A configurable fake like this (success/raises/delay) is reused across many tests in a file rather than writing a dozen tiny single-purpose fakes — this is the standard shape for testing an executor's retry/timeout/cancellation behavior.

## ABC Enforcement: Parametrized Missing-Member Tests

Every ABC in the platform has a test proving that a subclass missing *any one* required member cannot be instantiated:

```python
_ALL_MEMBERS = ("describe", "health_check", "provider_name", "model_name")

@pytest.mark.parametrize("missing_member", _ALL_MEMBERS)
def test_a_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    namespace = {name: _stub(name) for name in _ALL_MEMBERS if name != missing_member}
    incomplete = type("IncompleteProvider", (ImageVisionProvider,), namespace)
    with pytest.raises(TypeError):
        incomplete()
```

This is what actually proves an ABC's contract is enforced, not merely documented in a docstring.

## Registry Testing

Every registry test file includes an **autouse isolation fixture** so tests never leak registrations into each other:

```python
@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(ToolRegistry._providers)
    ToolRegistry._providers.clear()
    yield
    ToolRegistry._providers.clear()
    ToolRegistry._providers.update(original)
```

And an explicit **Open/Closed test** proving a new entry needs no registry/factory code change:

```python
def test_adding_a_new_provider_requires_no_factory_modification():
    class _AnotherProvider(_FakeImageProvider):
        pass
    ImageVisionProviderRegistry.register(ProviderName.ANTHROPIC, _AnotherProvider)
    provider = ImageVisionProviderFactory.create(ProviderName.ANTHROPIC)
    assert isinstance(provider, _AnotherProvider)
```

Standard registry test coverage: starts empty, register-and-get, duplicate-registration rejection (`match="already registered"` — never a more specific string, so it survives message-wording changes), `overwrite=True` replacement, unregister, clear, and (where relevant) never-shares-storage-across-subclasses.

## Execution Engine Testing

A full executor test suite (`test_vision_execution.py`, `test_runtime_execution.py`, `test_tool_execution.py`) covers, at minimum:

- Successful execution.
- Event ordering (`*_STARTED` → capability/content events → `*_COMPLETED`/`*_FAILED`), asserted via a subscribed list.
- Hook call ordering, asserted via a recording hook.
- Identity propagation — the response's identity fields match the executing context's, and (separately) match `parent_shared.child()`'s expected values when a parent context is given.
- Retry: a flaky fake that fails N times then succeeds; assert final success and the retry count on the response's metrics.
- Retry exhaustion: a fake that always fails; assert final failure and the exact attempt count.
- The provider-error-is-not-retried distinction: a factory that always raises `AIProviderError`; assert exactly one call, not `max_retries + 1`.
- Timeout: a fake with an artificial `delay`, a short `RuntimeTimeout`.
- Cancellation before start, and cancellation between retries.
- Middleware onion ordering and short-circuit (a middleware that returns without calling `call_next`).
- Metrics propagation (`duration_ms`, `retry_count`, `execution_id`).
- Determinism — two independently-constructed executors given equivalent inputs produce equivalent outputs.
- Real registry/factory integration — at least one test using the actual registry/factory (not just an injected fake `provider_factory_map`), to prove the default wiring genuinely works end to end.

## Dataclass/Value-Object Testing

- Frozen: `pytest.raises(dataclasses.FrozenInstanceError)` on a mutation attempt.
- Immutable mapping fields: `isinstance(x.metadata, MappingProxyType)` and a `pytest.raises(TypeError)` on a mutation attempt against the returned mapping.
- Hashability, where relevant: `isinstance(hash(x), int)` — added platform-wide after the event-hashing gap was found (see [Event_System.md](../02_KERNEL/Event_System.md)); do not skip this for a new frozen dataclass that holds a `MappingProxyType` field and might ever be hashed.
- Subclass relationships, post-M19-completion-pass: `issubclass(YourEvent, GenericEvent)`, `issubclass(YourRegistry, GenericProviderRegistry)`, `issubclass(YourMiddleware, GenericMiddleware)` — proving a new type actually builds on the shared generic rather than merely resembling it.

## Regression Discipline

Run the **full** backend test suite (`python -m pytest -q`, not just the new files) plus `ruff check app scripts settings.py` after any change — not just the package you touched. The platform's own standing baseline is zero regressions tolerated; the M19 completion pass, for example, touched seven subsystems in one pass specifically because each migration was verified against the full suite (1987 → 2016 passing, zero failures) before moving to the next.

## What's Missing Today

- No `import-linter`-style automated enforcement of [Dependency_Rules.md](../01_ARCHITECTURE/Dependency_Rules.md) — violations are currently caught by manual grep-checking, not CI. See the ADS-1 sprint's recommendations.
- No property-based testing (e.g. Hypothesis) anywhere in the suite — all tests are example-based.
- No load/performance testing for any execution engine.
