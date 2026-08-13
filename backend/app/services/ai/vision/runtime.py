"""VisionRuntime - the sole public entry point for executing vision
requests. Exactly like AIRuntime: every future agent (or the Vision
Framework's own future concrete providers) calls VisionRuntime rather
than reaching into a provider, an executor, or a registry directly.

Knows only the four *ProviderFactory/*ProviderRegistry pairs - never a
specific vendor.
"""

from app.services.ai.vision.analysis.provider_factory import AnalysisProviderFactory
from app.services.ai.vision.analysis.registry import AnalysisProviderRegistry
from app.services.ai.vision.capabilities.enums import VisionCapabilityCategory
from app.services.ai.vision.document.provider_factory import DocumentVisionProviderFactory
from app.services.ai.vision.document.registry import DocumentVisionProviderRegistry
from app.services.ai.vision.events import VisionEventPublisher
from app.services.ai.vision.execution import VisionExecutor
from app.services.ai.vision.extraction.provider_factory import ExtractionProviderFactory
from app.services.ai.vision.extraction.registry import ExtractionProviderRegistry
from app.services.ai.vision.hooks import VisionHook
from app.services.ai.vision.image.provider_factory import ImageVisionProviderFactory
from app.services.ai.vision.image.registry import ImageVisionProviderRegistry
from app.services.ai.vision.middleware import VisionMiddleware
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.request import VisionRequest
from app.services.ai.vision.response import VisionResponse

# Keyed by VisionCapabilityCategory - see the identical rationale in
# execution.py's _CAPABILITY_METHOD/_CAPABILITY_FACTORY/_CAPABILITY_EVENT.
_REGISTRIES: dict[VisionCapabilityCategory, type] = {
    VisionCapabilityCategory.IMAGE: ImageVisionProviderRegistry,
    VisionCapabilityCategory.DOCUMENT: DocumentVisionProviderRegistry,
    VisionCapabilityCategory.EXTRACTION: ExtractionProviderRegistry,
    VisionCapabilityCategory.ANALYSIS: AnalysisProviderRegistry,
}

_FACTORIES = {
    VisionCapabilityCategory.IMAGE: ImageVisionProviderFactory.create,
    VisionCapabilityCategory.DOCUMENT: DocumentVisionProviderFactory.create,
    VisionCapabilityCategory.EXTRACTION: ExtractionProviderFactory.create,
    VisionCapabilityCategory.ANALYSIS: AnalysisProviderFactory.create,
}


class VisionRuntime:
    def __init__(
        self,
        middleware: tuple[VisionMiddleware, ...] = (),
        hooks: tuple[VisionHook, ...] = (),
        event_publisher: VisionEventPublisher | None = None,
        max_retries: int = 0,
        executor: VisionExecutor | None = None,
    ) -> None:
        self.executor = executor or VisionExecutor(
            middleware=middleware,
            hooks=hooks,
            event_publisher=event_publisher,
            max_retries=max_retries,
        )

    def execute(self, request: VisionRequest) -> VisionResponse:
        return self.executor.execute(request)

    def health(self) -> dict[tuple[VisionCapabilityCategory, ProviderName], bool]:
        """Report health for every currently registered provider, across
        every capability. A provider that fails to construct or whose
        health_check() raises is reported unhealthy rather than
        propagating the failure."""
        report: dict[tuple[VisionCapabilityCategory, ProviderName], bool] = {}
        for category, registry in _REGISTRIES.items():
            factory = _FACTORIES[category]
            for provider_name in registry.all_registered():
                try:
                    provider = factory(provider_name)
                    report[(category, provider_name)] = provider.health_check()
                except Exception:  # noqa: BLE001 - a health report must never raise
                    report[(category, provider_name)] = False
        return report

    def capabilities(self) -> dict[tuple[VisionCapabilityCategory, ProviderName], object]:
        report: dict[tuple[VisionCapabilityCategory, ProviderName], object] = {}
        for category, registry in _REGISTRIES.items():
            factory = _FACTORIES[category]
            for provider_name in registry.all_registered():
                try:
                    provider = factory(provider_name)
                    report[(category, provider_name)] = provider.capabilities()
                except Exception:  # noqa: BLE001
                    continue
        return report

    def providers(self) -> dict[VisionCapabilityCategory, tuple[ProviderName, ...]]:
        return {category: tuple(registry.all_registered().keys()) for category, registry in _REGISTRIES.items()}
