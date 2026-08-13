from dataclasses import dataclass


@dataclass(frozen=True)
class ModelIdentity:
    """A provider-independent descriptor of a specific AI model.

    provider is a plain string, not app.services.ai.providers.enums.ProviderName -
    required by this task, and consistent with every other kernel type's
    rule against importing anything from elsewhere in app.services.ai.

    This overlaps conceptually with app.services.ai.shared.types.ProviderCapabilities
    (both have supports_streaming/supports_tools/supports_reasoning-shaped
    fields) - that overlap is intentional, not an oversight: ModelIdentity
    additionally identifies *which* model (family/model_name/version), and
    duplicating the capability flags here is the price of the kernel
    never importing from shared/. Only provider is required; every other
    field is genuinely optional descriptive data a caller may not have.
    """

    provider: str
    family: str | None = None
    model_name: str | None = None
    version: str | None = None
    context_window: int | None = None
    supports_streaming: bool = False
    supports_tools: bool = False
    supports_images: bool = False
    supports_audio: bool = False
    supports_reasoning: bool = False
