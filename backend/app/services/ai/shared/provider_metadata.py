from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderMetadata:
    """Descriptive, non-functional information about a provider.

    Useful for future routing/selection decisions and UI (e.g. "prefer
    local providers," "show the vendor's homepage/license") - not for
    making a request itself. Distinct from:

    - ProviderCapabilities (shared/types.py): what a model can *do*.
    - app.services.ai.kernel.model.ModelIdentity: the OS-kernel's own
      provider-independent model descriptor, deliberately duplicated
      rather than imported here since the kernel never imports from
      providers/conversation/shared and providers (which import this
      type) are expected to expose their own metadata directly - the two
      types serve different layers of the platform.

    Only provider_name is required; everything else is optional
    descriptive data a provider may not have (or may not want to
    disclose, e.g. no public homepage for an internal/local model).
    """

    provider_name: str
    vendor: str | None = None
    homepage: str | None = None
    license: str | None = None
    supports_local: bool = False
    supports_cloud: bool = True
    context_window: int | None = None
    max_output_tokens: int | None = None
