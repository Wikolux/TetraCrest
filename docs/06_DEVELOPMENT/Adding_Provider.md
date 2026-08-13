# Adding a Provider

This guide covers adding a concrete vendor provider — for Conversation or for any of Vision's four capabilities. As of M19, **no concrete provider exists anywhere in this platform** — every framework has been proven provider-agnostic using hand-written test fakes only. You would be the first real one.

## The Shape You're Implementing

```
Agent → Capability Framework → Provider (abstract contract, already built) → Your Provider Implementation (new)
```

Nothing above the provider layer changes. You are filling in the last box.

## Steps: Conversation Provider (example: OpenAI)

1. **Create a new module** — e.g. `app/services/ai/conversation/providers/openai_provider.py`. This is the **only** file allowed to import the OpenAI SDK/HTTP client. See [Dependency_Rules.md](../01_ARCHITECTURE/Dependency_Rules.md)'s "no vendor coupling above the provider layer" rule.

2. **Implement `ConversationProvider`.**

```python
from app.services.ai.conversation.base_provider import ConversationProvider

class OpenAIConversationProvider(ConversationProvider):
    def __init__(self, config: ConversationProviderConfig): ...

    def generate(self, prompt_package: PromptPackage) -> ConversationResponse:
        # call the vendor SDK/HTTP client here, translate its response into ConversationResponse
        ...

    def health_check(self) -> bool: ...

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str: ...

    # Override only if genuinely supported:
    def capabilities(self) -> ProviderCapabilities: ...
    async def stream(self, prompt_package: PromptPackage) -> AsyncIterator[ConversationStreamChunk]: ...
```

3. **Translate vendor errors, don't leak them.** Your `generate()` should raise `AIProviderError` (or let a generic exception propagate, which `RuntimeExecutor` will catch and convert) — never let a vendor-specific exception type escape into code that isn't allowed to know about your vendor.

4. **Register — typically at import time.**

```python
ConversationProviderRegistry.register(ProviderName.OPENAI, OpenAIConversationProvider)
```

5. **Do not modify `ConversationProviderFactory`, `AIRuntime`, or `RuntimeExecutor`.** If you find yourself editing any of those three, something has gone wrong — the whole point of the registry/factory pattern is that adding a provider never requires touching them.

6. **Test with the real registry, not just a fake.** In addition to your own provider's unit tests (mocking/faking the actual vendor call, since real API calls don't belong in the test suite), add an integration-style test registering your real provider class and resolving it through `ConversationProviderFactory.create(ProviderName.OPENAI)` — this is what proves the registration actually works end to end, following the pattern in `test_vision_image.py`'s `test_adding_a_new_provider_requires_no_factory_modification`.

## Steps: Vision Provider

Identical shape, for whichever of the four capabilities you're implementing:

```python
from app.services.ai.vision.image.base_provider import ImageVisionProvider

class YourVendorImageProvider(ImageVisionProvider):
    def describe(self, request: VisionRequest) -> VisionResponse: ...
    def health_check(self) -> bool: ...
    @property
    def provider_name(self) -> ProviderName: ...
    @property
    def model_name(self) -> str: ...

ImageVisionProviderRegistry.register(ProviderName.YOUR_VENDOR, YourVendorImageProvider)
```

Repeat for `DocumentVisionProvider`/`understand()`, `ExtractionProvider`/`extract()`, `AnalysisProvider`/`analyze()` as needed — these are four independent registries, so a vendor can be registered for one capability without needing to support all four.

## Configuration

Both Conversation and Vision providers are constructed from `BaseProviderConfig` (`api_key`, `base_url`, `timeout`, `max_retries`, `headers`, `metadata`) — or `ConversationProviderConfig` for Conversation specifically. If your vendor genuinely needs a field neither covers, extend the relevant config type rather than working around it with `metadata`.

## Checklist

- [ ] Implementation lives in its own module — no other file imports the vendor SDK
- [ ] Implements every abstract member of the relevant provider ABC
- [ ] `health_check()` reflects real reachability, not just "config looks valid" (unless that's a deliberate, documented choice — see `OpenAIEmbeddingProvider.health_check()`'s API-key-presence-only check in `app/services/embedding/` for a precedent of documenting this choice explicitly)
- [ ] Vendor-specific exceptions are translated, never leaked past this module
- [ ] Registered via the relevant registry, typically at import time
- [ ] No modification to the factory, runtime/executor, or any framework-level code
- [ ] Both a unit test (faked vendor call) and an integration-style test resolving through the real factory
