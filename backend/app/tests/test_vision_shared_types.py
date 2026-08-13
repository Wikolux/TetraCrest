import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.vision.shared.types import (
    BoundingBox,
    DetectedObject,
    DocumentMetadata,
    ExtractedTable,
    ExtractedText,
    ImageMetadata,
    VisionCapabilities,
    VisionMetadata,
)


def test_bounding_box_construction():
    box = BoundingBox(x=1.0, y=2.0, width=3.0, height=4.0)

    assert (box.x, box.y, box.width, box.height) == (1.0, 2.0, 3.0, 4.0)


def test_bounding_box_is_frozen():
    box = BoundingBox(x=0, y=0, width=1, height=1)

    with pytest.raises(dataclasses.FrozenInstanceError):
        box.x = 5


def test_detected_object_defaults():
    obj = DetectedObject(label="cat")

    assert obj.confidence == 1.0
    assert obj.bounding_box is None
    assert isinstance(obj.metadata, MappingProxyType)


def test_detected_object_metadata_cannot_be_mutated():
    obj = DetectedObject(label="cat", metadata={"a": 1})

    with pytest.raises(TypeError):
        obj.metadata["a"] = 2


def test_extracted_text_defaults():
    text = ExtractedText(content="hello")

    assert text.confidence == 1.0
    assert text.bounding_box is None
    assert text.language is None


def test_extracted_table_defaults():
    table = ExtractedTable()

    assert table.rows == ()
    assert table.caption is None


def test_extracted_table_rows_is_coerced_to_a_tuple_of_tuples():
    table = ExtractedTable(rows=[["a", "b"], ["c", "d"]])

    assert table.rows == (("a", "b"), ("c", "d"))


def test_vision_capabilities_defaults():
    capabilities = VisionCapabilities()

    assert capabilities.declared == frozenset()
    assert capabilities.has("ocr") is False


def test_vision_capabilities_has_reflects_declared():
    capabilities = VisionCapabilities(declared={"ocr", "describe"})

    assert capabilities.has("ocr") is True
    assert capabilities.has("unknown") is False


def test_vision_capabilities_declared_is_coerced_to_a_frozenset():
    capabilities = VisionCapabilities(declared=["ocr"])

    assert isinstance(capabilities.declared, frozenset)


def test_image_metadata_defaults():
    metadata = ImageMetadata()

    assert metadata.width is None
    assert metadata.height is None
    assert metadata.format is None
    assert metadata.size_bytes is None


def test_document_metadata_defaults():
    metadata = DocumentMetadata()

    assert metadata.page_count is None
    assert metadata.format is None


def test_vision_metadata_defaults():
    metadata = VisionMetadata()

    assert metadata.capability_category is None
    assert metadata.input_count == 1
    assert isinstance(metadata.extra, MappingProxyType)


def test_vision_metadata_extra_cannot_be_mutated():
    metadata = VisionMetadata(extra={"a": 1})

    with pytest.raises(TypeError):
        metadata.extra["a"] = 2


def test_all_value_objects_are_frozen():
    for instance in (
        BoundingBox(x=0, y=0, width=1, height=1),
        DetectedObject(label="x"),
        ExtractedText(content="x"),
        ExtractedTable(),
        VisionCapabilities(),
        ImageMetadata(),
        DocumentMetadata(),
        VisionMetadata(),
    ):
        first_field = dataclasses.fields(instance)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(instance, first_field, "changed")
