"""VisionEvent/VisionEventPublisher - built directly on GenericEvent/
EventPublisher (app.services.ai.shared.events) rather than hand-copying
the typed-event-plus-sync-pub/sub shape a sixth time. Subclassing (not
just a type alias) gives Vision its own distinct, isinstance-checkable
type while reusing 100% of the field shape and dispatch logic.

Every event carries execution_id, correlation_id, and timestamp -
inherited directly from GenericEvent, exactly as required.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


class VisionEventType(StrEnum):
    VISION_STARTED = "vision_started"
    IMAGE_ANALYZED = "image_analyzed"
    DOCUMENT_ANALYZED = "document_analyzed"
    TEXT_EXTRACTED = "text_extracted"
    TABLE_EXTRACTED = "table_extracted"
    OBJECTS_DETECTED = "objects_detected"
    VISION_COMPLETED = "vision_completed"
    VISION_FAILED = "vision_failed"


@dataclass(frozen=True, kw_only=True)
class VisionEvent(GenericEvent):
    event_type: VisionEventType

    __hash__ = hash_event


class VisionEventPublisher(EventPublisher[VisionEvent]):
    pass
