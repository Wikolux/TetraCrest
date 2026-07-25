import re

# Add a new category by adding one entry here - nothing else needs to change.
# Keywords are matched case-insensitively on whole words/phrases against the
# combined title + content + original_filename + mime_type text; the
# category with the most matches wins.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Business": [
        "business plan",
        "business strategy",
        "stakeholder",
        "business model",
        "partnership agreement",
        "business development",
        "market analysis",
        "growth strategy",
        "business proposal",
    ],
    "Finance": [
        "invoice",
        "budget",
        "revenue",
        "expense",
        "forecast",
        "audit",
        "balance sheet",
        "cash flow",
        "financial statement",
        "financial report",
        "accounting",
        "payroll",
    ],
    "Legal": [
        "contract",
        "agreement",
        "compliance",
        "regulation",
        "litigation",
        "lawsuit",
        "liability",
        "legal counsel",
        "terms and conditions",
        "non-disclosure agreement",
        "intellectual property",
    ],
    "Engineering": [
        "api",
        "database",
        "deployment",
        "architecture",
        "codebase",
        "infrastructure",
        "algorithm",
        "backend",
        "frontend",
        "software engineering",
        "pull request",
        "source code",
    ],
    "Product": [
        "roadmap",
        "feature request",
        "release notes",
        "backlog",
        "user story",
        "wireframe",
        "prototype",
        "product requirements",
        "mvp",
    ],
    "Marketing": [
        "campaign",
        "branding",
        "social media",
        "advertisement",
        "seo",
        "content strategy",
        "target audience",
        "promotion",
    ],
    "Sales": [
        "sales quota",
        "sales pipeline",
        "lead generation",
        "prospect",
        "crm",
        "closing the deal",
        "commission",
    ],
    "HR": [
        "recruitment",
        "onboarding",
        "employee benefits",
        "hiring",
        "performance review",
        "human resources",
        "workplace policy",
    ],
    "Technology": [
        "technology",
        "innovation",
        "digital transformation",
        "cloud computing",
        "cybersecurity",
        "artificial intelligence",
        "automation",
        "tech stack",
        "it infrastructure",
    ],
    "Research": [
        "hypothesis",
        "methodology",
        "survey",
        "research findings",
        "literature review",
        "experiment",
        "data analysis",
        "peer review",
    ],
    "Education": [
        "curriculum",
        "course syllabus",
        "training program",
        "lesson plan",
        "classroom",
        "tutorial",
        "workshop",
        "student assessment",
    ],
    "Operations": [
        "supply chain",
        "logistics",
        "procurement",
        "inventory management",
        "process improvement",
        "workflow",
    ],
}

DEFAULT_CATEGORY = "General"


class ClassificationService:
    """Deterministic, keyword-based document classifier.

    No LLM calls, no embeddings, no external APIs - just a case-insensitive,
    whole-word/phrase keyword count per category against whatever text is
    available (title, content, original_filename, mime_type). The category
    with the most keyword hits wins; ties are broken by each category's
    declaration order in CATEGORY_KEYWORDS. If nothing matches, the result
    is "General".

    Reusable across every ingestion source: sources with no extracted text
    (image/audio/video) can still pass title/original_filename/mime_type
    and get a real classification if the filename or title happens to
    carry a signal, falling back to "General" otherwise.
    """

    def classify(
        self,
        title: str | None = None,
        content: str | None = None,
        original_filename: str | None = None,
        mime_type: str | None = None,
    ) -> str:
        text = " ".join(
            part for part in (title, content, original_filename, mime_type) if part
        ).lower()

        best_category = DEFAULT_CATEGORY
        best_score = 0
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if self._contains(text, keyword))
            if score > best_score:
                best_score = score
                best_category = category

        return best_category

    @staticmethod
    def _contains(text: str, keyword: str) -> bool:
        pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
        return re.search(pattern, text) is not None
