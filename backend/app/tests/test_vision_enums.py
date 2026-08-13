from app.services.ai.vision.capabilities.enums import (
    AnalysisCapability,
    DocumentCapability,
    ExtractionCapability,
    ImageCapability,
    VisionCapabilityCategory,
)
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.providers.enums import ProviderName as PlatformProviderName


def test_vision_provider_name_is_the_platform_provider_name_not_a_copy():
    assert ProviderName is PlatformProviderName


def test_vision_capability_category_has_the_four_services():
    assert {member.value for member in VisionCapabilityCategory} == {"image", "document", "extraction", "analysis"}


def test_image_capability_has_every_documented_capability():
    assert {member.value for member in ImageCapability} == {
        "describe",
        "identify_objects",
        "scene_understanding",
        "classification",
        "captioning",
    }


def test_document_capability_has_every_documented_capability():
    assert {member.value for member in DocumentCapability} == {
        "pdf_understanding",
        "scanned_document",
        "invoice",
        "form",
        "contract",
        "report",
    }


def test_extraction_capability_has_every_documented_capability():
    assert {member.value for member in ExtractionCapability} == {
        "ocr",
        "table_extraction",
        "structured_data_extraction",
        "key_value_extraction",
    }


def test_analysis_capability_has_every_documented_capability():
    assert {member.value for member in AnalysisCapability} == {
        "chart_analysis",
        "graph_analysis",
        "ui_screenshot_analysis",
        "architecture_diagram_analysis",
        "flowchart_interpretation",
    }
