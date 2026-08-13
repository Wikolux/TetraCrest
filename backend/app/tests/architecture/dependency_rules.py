"""The dependency validator: AST-based import graph analysis for
app/services/ai/ package boundaries.

This module is the executable form of docs/01_ARCHITECTURE/Dependency_Rules.md.
It never imports the modules it inspects and never greps source text - every
import statement is discovered by parsing each file with the `ast` module,
so a violation is caught even if it's written in a way that would dodge a
text search (e.g. a multi-line `from ... import (...)`).

Two independent checks are exposed:

- find_boundary_violations(): every app.services.ai-internal import is
  checked against a declared per-boundary allow-list.
- find_vendor_import_violations(): no module under app/services/ai may
  import a known vendor SDK, HTTP client, or OCR/image library - as of this
  writing there are zero concrete providers anywhere in the platform, so
  this is trivially satisfied today and exists to catch the first violation
  the moment one is introduced.

Nothing here changes production behavior; this package is test-only
infrastructure.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

AI_ROOT_PACKAGE = "app.services.ai"
AI_ROOT_DIR = Path(__file__).resolve().parents[2] / "services" / "ai"

# Boundaries ordered from most to least specific - classify_module() does a
# longest-prefix match, so "agents.specialists.research" must be checked
# before "agents.specialists" before "agents", or every specialist/executive
# module would be misclassified as plain "agents".
_BOUNDARIES_BY_SPECIFICITY: tuple[str, ...] = (
    "agents.specialists.research",
    "agents.specialists.personal_intelligence",
    "agents.specialists.product_management",
    "agents.specialists",
    "agents.executive",
    "agents",
    "tools",
    "vision",
    "runtime",
    "conversation",
    "kernel",
    "providers",
    "capabilities",
    "shared",
)

# boundary -> the set of other app.services.ai boundaries it may depend on.
# Mirrors docs/01_ARCHITECTURE/Dependency_Rules.md exactly. A boundary never
# needs to list itself - intra-boundary imports are always permitted.
ALLOWED_DEPENDENCIES: dict[str, frozenset[str]] = {
    # shared/response.py's ProviderResponse needs ProviderName to know which
    # provider produced a response - providers/ is a pure, dependency-free
    # enum leaf, so this creates no cycle risk.
    "shared": frozenset({"providers"}),
    "providers": frozenset(),
    "capabilities": frozenset(),
    # kernel's default is empty on purpose - see MODULE_EXCEPTIONS below.
    "kernel": frozenset(),
    "runtime": frozenset({"shared", "conversation", "providers"}),
    "conversation": frozenset({"shared", "providers"}),
    "agents": frozenset({"shared", "kernel", "runtime"}),
    # ExecutiveAgent calls AIRuntime directly (its own conversational
    # capability, not only delegation), so it needs "runtime" and
    # "providers" (ProviderName) beyond the base agents/ allowance.
    "agents.executive": frozenset({"agents", "agents.specialists", "shared", "kernel", "runtime", "providers"}),
    "agents.specialists": frozenset({"agents", "tools", "runtime", "shared", "kernel"}),
    # ResearchAgent holds a RuntimeAdapter but also constructs/reads
    # RuntimeRequest/RuntimeResponse directly (the adapter wraps the call,
    # not the value objects), and reuses ExecutionMetrics/ProviderName -
    # the same "runtime" and "providers" allowance as agents.executive,
    # plus "kernel" for ExecutionMetrics.
    "agents.specialists.research": frozenset(
        {"agents.specialists", "agents", "tools", "shared", "runtime", "kernel", "providers"}
    ),
    # PersonalIntelligenceAgent (CP-01) mirrors ResearchAgent exactly: a
    # RuntimeAdapter plus direct RuntimeRequest/RuntimeResponse/
    # ExecutionMetrics/ProviderName use - the identical allowance as
    # agents.specialists.research, for the identical reason.
    "agents.specialists.personal_intelligence": frozenset(
        {"agents.specialists", "agents", "tools", "shared", "runtime", "kernel", "providers"}
    ),
    # DiscoverySpecialist (CP-02, Milestone 3) holds a RuntimeAdapter and
    # also constructs/reads RuntimeRequest/RuntimeResponse/ExecutionMetrics/
    # ProviderName directly, the identical shape as ResearchAgent and
    # PersonalIntelligenceAgent - the same allowance, for the same reason.
    # This is CP-02's first dependency-boundary entry (Implementation_Plan.md
    # §15): Milestones 1-2 needed none, since their code never went beyond
    # AgentMemory/MemoryAdapter, already covered by the generic
    # "agents.specialists" boundary via longest-prefix match.
    "agents.specialists.product_management": frozenset(
        {"agents.specialists", "agents", "tools", "shared", "runtime", "kernel", "providers"}
    ),
    "tools": frozenset({"shared", "runtime", "kernel"}),
    "vision": frozenset({"shared", "runtime", "kernel", "providers"}),
}

# Named, single-module exceptions - deliberately narrower than a blanket
# boundary-level allowance, and they REPLACE (not extend) the boundary
# default for that one module. kernel/context.py is the Kernel's one
# sanctioned dependency outside itself (composing SharedExecutionContext);
# every other kernel module must depend on nothing outside the kernel.
MODULE_EXCEPTIONS: dict[str, frozenset[str]] = {
    "kernel.context": frozenset({"shared"}),
}

# Top-level module names of vendor SDKs / HTTP clients / OCR / image
# libraries. No module under app/services/ai may import any of these -
# every capability framework in this platform is provider-agnostic by
# construction, and a concrete provider implementation (none exist yet)
# is expected to live in its own module, outside this package's reach.
VENDOR_MODULE_BLOCKLIST: frozenset[str] = frozenset(
    {
        "openai",
        "anthropic",
        "google",
        "cohere",
        "mistralai",
        "groq",
        "requests",
        "httpx",
        "urllib3",
        "aiohttp",
        "boto3",
        "botocore",
        "azure",
        "cv2",
        "PIL",
        "pytesseract",
        "easyocr",
    }
)


@dataclass(frozen=True)
class ImportEdge:
    importing_module: str  # dotted, relative to app.services.ai, e.g. "agents.executive.dispatcher"
    imported: str  # the full dotted name as written in the source, e.g. "app.services.ai.tools.registry"


def iter_ai_python_files() -> list[Path]:
    return sorted(AI_ROOT_DIR.rglob("*.py"))


def module_name_for(path: Path) -> str:
    """The dotted module name of `path`, relative to app.services.ai."""
    relative = path.relative_to(AI_ROOT_DIR).with_suffix("")
    parts = relative.parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def classify_module(module: str) -> str | None:
    """The boundary a dotted module (relative to app.services.ai) belongs
    to, or None if it matches no known boundary (e.g. the empty string for
    app.services.ai's own top-level __init__.py)."""
    for boundary in _BOUNDARIES_BY_SPECIFICITY:
        if module == boundary or module.startswith(boundary + "."):
            return boundary
    return None


def _extract_imports(tree: ast.AST) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                imports.append(node.module)
    return imports


def build_import_edges() -> list[ImportEdge]:
    """Every import statement in every module under app/services/ai/,
    discovered via `ast.parse` - not by importing the modules, and not by
    searching their source text."""
    edges: list[ImportEdge] = []
    for path in iter_ai_python_files():
        module = module_name_for(path)
        tree = ast.parse(path.read_text(), filename=str(path))
        for imported in _extract_imports(tree):
            edges.append(ImportEdge(importing_module=module, imported=imported))
    return edges


def ai_os_internal_edges() -> list[tuple[str, str]]:
    """(importing_module, imported_module) pairs, both dotted and relative
    to app.services.ai, for every import that points at another module
    within app.services.ai. Imports of anything else (stdlib, prompt_builder,
    a vendor SDK, ...) are not internal edges and are excluded here."""
    prefix = AI_ROOT_PACKAGE + "."
    edges = []
    for edge in build_import_edges():
        if edge.imported == AI_ROOT_PACKAGE:
            edges.append((edge.importing_module, ""))
        elif edge.imported.startswith(prefix):
            edges.append((edge.importing_module, edge.imported[len(prefix) :]))
    return edges


def imported_boundaries_for(importer_boundary: str) -> set[str]:
    """Every other boundary that `importer_boundary` actually depends on
    today, discovered from the real import graph."""
    result: set[str] = set()
    for importing_module, imported_module in ai_os_internal_edges():
        if classify_module(importing_module) != importer_boundary:
            continue
        imported_boundary = classify_module(imported_module)
        if imported_boundary and imported_boundary != importer_boundary:
            result.add(imported_boundary)
    return result


def find_boundary_violations() -> list[str]:
    """Every AI-OS-internal import that violates ALLOWED_DEPENDENCIES
    (or, for a module with a named exception, that exception's allow-set),
    as human-readable strings."""
    violations = []
    for importing_module, imported_module in ai_os_internal_edges():
        importer_boundary = classify_module(importing_module)
        imported_boundary = classify_module(imported_module)
        if importer_boundary is None or imported_boundary is None:
            continue
        if importer_boundary == imported_boundary:
            continue  # intra-boundary imports are always fine

        if importing_module in MODULE_EXCEPTIONS:
            allowed = MODULE_EXCEPTIONS[importing_module]
        else:
            allowed = ALLOWED_DEPENDENCIES.get(importer_boundary, frozenset())

        if imported_boundary not in allowed:
            violations.append(
                f"{importing_module} (boundary={importer_boundary!r}) imports "
                f"{imported_module} (boundary={imported_boundary!r}), which is not "
                f"in the allowed set {sorted(allowed)!r}"
            )
    return violations


def find_vendor_import_violations() -> list[str]:
    """Every import anywhere under app/services/ai/ whose top-level module
    name is a known vendor SDK / HTTP client / OCR / image library."""
    violations = []
    for edge in build_import_edges():
        top_level = edge.imported.split(".", 1)[0]
        if top_level in VENDOR_MODULE_BLOCKLIST:
            violations.append(f"{edge.importing_module} imports vendor/HTTP/OCR/image module {edge.imported!r}")
    return violations
