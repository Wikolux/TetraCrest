"""BaseVisionProvider - the members every vision provider (Image/Document/
Extraction/Analysis) shares, mirroring ConversationProvider's own split
between fully-abstract core members (no generic default makes sense) and
concrete-with-safe-default optional ones.

Each of the four capability-specific ABCs (ImageVisionProvider/
DocumentVisionProvider/ExtractionProvider/AnalysisProvider) extends this
rather than each redefining health_check/provider_name/model_name/
initialize/shutdown/capabilities/metadata independently - the same
unification reasoning applied to registries/events/middleware in this
milestone, applied here to the provider contract itself. Deliberately
holds no "analyze"-shaped abstract method: each capability's primary verb
differs (describe/understand/extract/analyze), so that one abstract
method per capability is declared on the capability-specific subclass,
not here.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from app.services.ai.shared.provider_metadata import ProviderMetadata
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.shared.types import VisionCapabilities


class BaseVisionProvider(ABC):
    contract_version: ClassVar[str] = "1.0"

    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_name(self) -> ProviderName:
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    def initialize(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def capabilities(self) -> VisionCapabilities:
        return VisionCapabilities()

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(provider_name=str(self.provider_name))
