"""Vision capability taxonomy. VisionCapabilityCategory names the four
independent capability services (the four folders); each of the other
four enums names the fine-grained capabilities *within* one category -
these are what a concrete provider declares via VisionCapabilities.
"""

from enum import StrEnum


class VisionCapabilityCategory(StrEnum):
    IMAGE = "image"
    DOCUMENT = "document"
    EXTRACTION = "extraction"
    ANALYSIS = "analysis"


class ImageCapability(StrEnum):
    DESCRIBE = "describe"
    IDENTIFY_OBJECTS = "identify_objects"
    SCENE_UNDERSTANDING = "scene_understanding"
    CLASSIFICATION = "classification"
    CAPTIONING = "captioning"


class DocumentCapability(StrEnum):
    PDF_UNDERSTANDING = "pdf_understanding"
    SCANNED_DOCUMENT = "scanned_document"
    INVOICE = "invoice"
    FORM = "form"
    CONTRACT = "contract"
    REPORT = "report"


class ExtractionCapability(StrEnum):
    OCR = "ocr"
    TABLE_EXTRACTION = "table_extraction"
    STRUCTURED_DATA_EXTRACTION = "structured_data_extraction"
    KEY_VALUE_EXTRACTION = "key_value_extraction"


class AnalysisCapability(StrEnum):
    CHART_ANALYSIS = "chart_analysis"
    GRAPH_ANALYSIS = "graph_analysis"
    UI_SCREENSHOT_ANALYSIS = "ui_screenshot_analysis"
    ARCHITECTURE_DIAGRAM_ANALYSIS = "architecture_diagram_analysis"
    FLOWCHART_INTERPRETATION = "flowchart_interpretation"
