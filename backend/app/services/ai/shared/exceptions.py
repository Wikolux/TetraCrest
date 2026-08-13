class AIError(Exception):
    """Root exception for the entire AI platform (every capability, every
    provider).

    Every more specific AI platform error below inherits from this, so
    code that wants to catch "something in the AI platform failed"
    without caring exactly what can catch this one type - the same role
    EmbeddingProviderError/VectorStoreError play for their own
    subsystems, generalized here because this platform is many
    capabilities under one roof by design.
    """


class AIProviderError(AIError):
    """Raised when a provider cannot be resolved or constructed - e.g. an
    unsupported or unregistered provider name, or a duplicate
    registration attempt.

    Pre-existing type (this platform's original, and until now only,
    error type), kept with its exact name and behavior for backward
    compatibility: ConversationProviderFactory/ConversationProviderRegistry
    still raise this specific type for these specific cases. It now also
    inherits from AIError, so existing code catching AIProviderError
    keeps working unchanged, and new code can catch the broader AIError
    instead if it doesn't care which specific thing failed.
    """


class AuthenticationError(AIError):
    """The provider rejected the caller's credentials (invalid, expired,
    or missing API key)."""


class RateLimitError(AIError):
    """The provider reports the caller has been rate-limited."""


class TimeoutError(AIError):  # noqa: A001 - intentionally named to match the platform's error taxonomy
    """The provider did not respond in time.

    Shadows the builtin TimeoutError only for code that imports this name
    explicitly from this module (`from ...exceptions import TimeoutError`)
    - the builtin remains available everywhere else. Kept as named
    exactly because the platform's error vocabulary should read naturally
    ("raise TimeoutError(...)") rather than inventing an awkward
    alternative name to dodge a builtin that isn't actually being
    globally overridden.
    """


class ProviderUnavailableError(AIError):
    """The provider is temporarily unavailable (outage, maintenance,
    connection failure, ...)."""


class InvalidRequestError(AIError):
    """The request was malformed in a way the provider rejected."""


class ContentFilterError(AIError):
    """The provider refused to respond due to content-safety filtering."""


class QuotaExceededError(AIError):
    """The caller has exhausted an allotted quota.

    Distinct from RateLimitError: a rate limit is transient (retrying
    later helps), exhausting a quota implies no amount of waiting helps
    until the quota itself resets or is increased.
    """


class ModelNotFoundError(AIError):
    """The requested model does not exist, or is not accessible to the caller."""


class StreamingError(AIError):
    """A streaming-specific failure - e.g. a provider that doesn't
    support streaming being asked to stream (see
    ConversationProvider.stream()'s default implementation), or a stream
    that fails partway through."""
