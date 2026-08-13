"""Provider-neutral configuration objects.

Replaces passing primitive **kwargs straight into a provider's
constructor: a factory now hands a provider a typed, immutable config
object instead. BaseProviderConfig holds the fields that make sense for
literally any provider of any capability (connection/auth/observability);
each capability's config (ConversationProviderConfig today; a future
VisionProviderConfig, EmbeddingProviderConfig, ...) inherits from it and
adds only its own capability-specific fields.
"""

from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.shared.execution_types import Metadata


def _freeze_mapping(instance, field_name: str) -> None:
    value = getattr(instance, field_name)
    if not isinstance(value, MappingProxyType):
        object.__setattr__(instance, field_name, MappingProxyType(dict(value)))


@dataclass(frozen=True)
class BaseProviderConfig:
    """Configuration shared by every capability's provider config.

    Only fields that apply regardless of what a provider actually does:
    how to connect to it (api_key, base_url, headers), how patient to be
    (timeout, max_retries), and an escape hatch for anything else
    (metadata). No OpenAI-, Anthropic-, or any other vendor-specific
    field belongs here - or in any subclass - only in a future concrete
    provider's own constructor logic if it needs vendor-specific
    defaults.
    """

    api_key: str | None = None
    base_url: str | None = None
    timeout: float | None = None
    max_retries: int = 3
    headers: Metadata = field(default_factory=lambda: MappingProxyType({}))
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_mapping(self, "headers")
        _freeze_mapping(self, "metadata")


@dataclass(frozen=True)
class ConversationProviderConfig(BaseProviderConfig):
    """Configuration for a conversation-capable provider.

    Adds generation parameters on top of BaseProviderConfig's connection/
    auth fields. Every field is optional - a config can be constructed
    before a specific model/temperature/etc. is chosen (e.g. a factory
    default), and a concrete provider decides what, if anything, it
    requires to actually be set before it can serve requests.
    """

    model: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    organization: str | None = None
