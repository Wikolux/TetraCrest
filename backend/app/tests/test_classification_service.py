import pytest

from app.services.classification_service import ClassificationService

CASES = [
    (
        "Business",
        "Business Growth Strategy",
        "This business plan outlines our business strategy, stakeholder "
        "alignment, and business development goals for the next quarter.",
    ),
    (
        "Legal",
        "Master Service Agreement",
        "This contract outlines the liability and compliance obligations "
        "under the agreement, including terms and conditions for litigation.",
    ),
    (
        "Finance",
        "Q3 Financial Report",
        "This document covers revenue, budget forecast, and the balance "
        "sheet as reviewed in the audit.",
    ),
    (
        "Engineering",
        "Backend Architecture Overview",
        "This document describes the API design, database schema, and "
        "deployment infrastructure for the backend.",
    ),
    (
        "Product",
        "Product Roadmap 2026",
        "This roadmap describes upcoming feature requests, the backlog, "
        "and user story priorities for the MVP.",
    ),
    (
        "Marketing",
        "Q4 Marketing Campaign",
        "This campaign covers branding, social media strategy, and target "
        "audience for the new advertisement.",
    ),
    (
        "Sales",
        "Weekly Sales Update",
        "This document covers the sales pipeline, lead generation, and "
        "prospect outreach, plus commission for closing the deal.",
    ),
    (
        "HR",
        "New Hire Onboarding Guide",
        "This document covers recruitment, onboarding, employee benefits, "
        "and the performance review process for human resources.",
    ),
    (
        "Technology",
        "Cloud Migration Plan",
        "This document covers our digital transformation, cloud computing "
        "strategy, cybersecurity posture, and automation initiatives.",
    ),
    (
        "Research",
        "Customer Behavior Study",
        "This research findings document describes the hypothesis, "
        "methodology, and literature review used in the experiment.",
    ),
    (
        "Education",
        "New Employee Training Program",
        "This document covers the course syllabus, lesson plan, classroom "
        "activities, and student assessment for the workshop.",
    ),
    (
        "Operations",
        "Warehouse Process Guide",
        "This document covers supply chain, logistics, procurement, and "
        "inventory management as part of process improvement.",
    ),
]


@pytest.mark.parametrize("expected,title,content", CASES)
def test_classifies_known_categories(expected, title, content):
    result = ClassificationService().classify(title=title, content=content)
    assert result == expected


def test_unknown_document_falls_back_to_general():
    result = ClassificationService().classify(
        title="Random Notes",
        content="Just a bunch of unrelated thoughts about lunch and the weather today.",
    )
    assert result == "General"


def test_empty_title_and_content_falls_back_to_general():
    assert ClassificationService().classify(title="", content="") == "General"


def test_no_arguments_do_not_raise_and_default_to_general():
    assert ClassificationService().classify() == "General"


def test_none_title_and_content_do_not_raise():
    assert ClassificationService().classify(title=None, content=None) == "General"


def test_classification_is_case_insensitive():
    result = ClassificationService().classify(
        title="INVOICE AND BUDGET",
        content="Please review the REVENUE forecast and AUDIT results.",
    )
    assert result == "Finance"


def test_partial_word_does_not_false_match():
    # "hr" is an HR keyword; embedding it inside other words should not
    # spuriously match.
    result = ClassificationService().classify(
        title="Chris's Architecture Notes",
        content="This describes the API, database, and backend infrastructure.",
    )
    assert result == "Engineering"


def test_classification_can_be_driven_by_original_filename_alone():
    result = ClassificationService().classify(
        title="Untitled",
        content="",
        original_filename="invoice.pdf",
        mime_type="application/pdf",
    )
    assert result == "Finance"


def test_classification_with_no_signal_in_any_field_is_general():
    result = ClassificationService().classify(
        title="Untitled",
        content="",
        original_filename="photo.png",
        mime_type="image/png",
    )
    assert result == "General"
