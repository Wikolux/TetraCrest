"""Architecture enforcement tests - the executable form of
docs/01_ARCHITECTURE/Dependency_Rules.md.

Every test here inspects the real import graph of app/services/ai/, built
by parsing source with `ast` (see dependency_rules.py) - never by grepping
text and never by importing the inspected modules. A pull request that
introduces an illegal cross-package import fails this suite the same run
as any other regression; there is no separate, optional lint step to skip.

This suite adds no runtime dependency and changes no production behavior -
it is purely test-time static analysis.
"""

from dependency_rules import (
    ALLOWED_DEPENDENCIES,
    classify_module,
    find_boundary_violations,
    find_vendor_import_violations,
    imported_boundaries_for,
    iter_ai_python_files,
    module_name_for,
)


def _format(violations: list[str]) -> str:
    return "\n".join(f"  - {v}" for v in violations)


# --- the comprehensive sweep -----------------------------------------------------------------


def test_no_package_boundary_violations_anywhere_in_the_ai_operating_system():
    """Every AI-OS-internal import, platform-wide, must be in its
    importer's declared allow-list. This is the single test that would
    catch a violation in a boundary not called out individually below
    (conversation, providers, capabilities, agents.executive,
    agents.specialists, agents.specialists.research)."""
    violations = find_boundary_violations()
    assert violations == [], "Illegal cross-package import(s) found:\n" + _format(violations)


def test_no_vendor_http_or_ocr_imports_anywhere_in_the_ai_operating_system():
    """No concrete provider exists yet anywhere in this platform - every
    capability framework is proven provider-agnostic using test fakes
    only. This test is what keeps that true: it fails the moment any
    module imports a vendor SDK, HTTP client, or OCR/image library."""
    violations = find_vendor_import_violations()
    assert violations == [], "Vendor/HTTP/OCR/image import(s) found:\n" + _format(violations)


# --- rule-table self-check --------------------------------------------------------------------


def test_every_declared_boundary_actually_matches_at_least_one_real_module():
    """Guards against a typo in ALLOWED_DEPENDENCIES silently matching
    nothing (e.g. renaming a package without updating the rule table)."""
    real_boundaries = {classify_module(module_name_for(p)) for p in iter_ai_python_files()}
    for boundary in ALLOWED_DEPENDENCIES:
        assert boundary in real_boundaries, (
            f"Boundary {boundary!r} in ALLOWED_DEPENDENCIES matches no real module - "
            "check for a rename or typo in dependency_rules.py"
        )


def test_every_python_file_under_app_services_ai_is_classified():
    """Guards against a new top-level package being added under
    app/services/ai/ without also adding it to the boundary list -
    an unclassified module is silently exempt from every check above."""
    unclassified = [
        module_name_for(p) for p in iter_ai_python_files() if classify_module(module_name_for(p)) is None
    ]
    # app.services.ai's own top-level __init__.py has no package of its own
    # to classify into and is expected to be the only exemption.
    unclassified = [m for m in unclassified if m != ""]
    assert unclassified == [], (
        "Module(s) not classified into any known boundary - add the new "
        f"package to _BOUNDARIES_BY_SPECIFICITY in dependency_rules.py: {unclassified}"
    )


# --- named tests matching the documented rules, per boundary ----------------------------------


def test_kernel_boundary_forbidden_dependencies():
    forbidden = {
        "runtime",
        "agents",
        "agents.executive",
        "agents.specialists",
        "agents.specialists.research",
        "tools",
        "vision",
        "conversation",
    }
    violated = imported_boundaries_for("kernel") & forbidden
    assert not violated, f"Kernel illegally depends on: {sorted(violated)}"


def test_kernel_context_is_the_only_kernel_module_allowed_to_import_outside_the_kernel():
    """A stricter, independent check of the Kernel's isolation than the
    allow-list alone: even if a future change widened ALLOWED_DEPENDENCIES
    or MODULE_EXCEPTIONS for "kernel", this test still names the one exact
    module (kernel.context) allowed to do it."""
    from dependency_rules import ai_os_internal_edges

    for importing_module, imported_module in ai_os_internal_edges():
        if classify_module(importing_module) != "kernel":
            continue
        imported_boundary = classify_module(imported_module)
        if imported_boundary is None or imported_boundary == "kernel":
            continue
        assert importing_module == "kernel.context", (
            f"{importing_module} imports outside the kernel ({imported_module}); "
            "only kernel.context is a sanctioned exception (composing SharedExecutionContext)"
        )


def test_runtime_boundary_forbidden_dependencies():
    forbidden = {
        "agents",
        "agents.executive",
        "agents.specialists",
        "agents.specialists.research",
        "vision",
        "tools",
    }
    violated = imported_boundaries_for("runtime") & forbidden
    assert not violated, f"Runtime illegally depends on: {sorted(violated)}"


def test_agents_boundary_forbidden_dependencies():
    forbidden = {"vision", "tools", "conversation", "agents.executive", "agents.specialists"}
    violated = imported_boundaries_for("agents") & forbidden
    assert not violated, f"Agents (framework) illegally depends on: {sorted(violated)}"


def test_vision_boundary_forbidden_dependencies():
    forbidden = {
        "agents",
        "agents.executive",
        "agents.specialists",
        "agents.specialists.research",
        "tools",
        "conversation",
    }
    violated = imported_boundaries_for("vision") & forbidden
    assert not violated, f"Vision illegally depends on: {sorted(violated)}"


def test_tools_boundary_forbidden_dependencies():
    forbidden = {
        "agents",
        "agents.executive",
        "agents.specialists",
        "agents.specialists.research",
        "vision",
    }
    violated = imported_boundaries_for("tools") & forbidden
    assert not violated, f"Tools illegally depends on: {sorted(violated)}"


def test_conversation_boundary_forbidden_dependencies():
    forbidden = {"runtime", "agents", "tools", "vision"}
    violated = imported_boundaries_for("conversation") & forbidden
    assert not violated, f"Conversation illegally depends on: {sorted(violated)}"


def test_executive_never_imports_a_specific_specialist():
    forbidden = {"agents.specialists.research"}
    violated = imported_boundaries_for("agents.executive") & forbidden
    assert not violated, f"Executive illegally depends on a concrete specialist: {sorted(violated)}"


def test_specialist_framework_never_imports_the_executive_or_a_concrete_specialist():
    forbidden = {"agents.executive", "agents.specialists.research"}
    violated = imported_boundaries_for("agents.specialists") & forbidden
    assert not violated, f"Specialist framework illegally depends on: {sorted(violated)}"
