# Capability Routing

This document surveys **every** dispatch/routing mechanism in the AI Operating System and states, for each, whether it is capability-based (routes on "what can handle this," using a closed enum) or identity/name-based (routes on "which specific thing, by its own label"), and why. It is the record of the M20.4 analysis: what was changed, what was reviewed and deliberately left alone, and what remains open.

**Constraint honored throughout this pass**: no behavior change. Every enum used for routing already existed before M20.4 (reused, never invented); where a field's *type* changed from `str` to an enum, the enum is a `StrEnum` whose members are string-equal and string-hash-equal to the literal values previously used, so every existing caller, dict lookup, and test continues to behave identically.

## The Capability Enums, and What Each Actually Drives

| Enum | Package | Drives routing for | Status before M20.4 | Status after M20.4 |
|---|---|---|---|---|
| `AgentCapability` | `agents/enums.py` | `Dispatcher.dispatch()` (Executive → agent instance) | Already capability-based | Unchanged — already correct |
| `ToolCapability` | `tools/enums.py` | `ToolDiscovery.by_capability()`, `PermissionPolicy` (via `ToolPermission`, a sibling enum) | Already capability-based | Unchanged — already correct |
| `SpecialistTaskType` | `agents/specialists/shared/task.py` | `SpecialistDispatcher.dispatch_by_task_type()` | Already capability-based | Unchanged — already correct |
| `VisionCapabilityCategory` | `vision/capabilities/enums.py` | **Now**: `VisionRequest.capability_category`, `VisionExecutor`'s dispatch tables, `VisionRuntime`'s registry/factory maps | Enum existed, but the actual routing used raw string literals (`"image"`, `"document"`, ...) — the enum was defined and never referenced by the routing code | **Fixed**: routing now keyed by the enum itself |
| `Capability` (platform-wide) | `ai/capabilities/enums.py` | Nothing | Unused by any production code | Still unused — see "Deliberately Not Wired" below |

## What Changed

### Vision: `capability_category` — `str` → `VisionCapabilityCategory`

Before M20.4, `VisionRequest.capability_category` was typed `str`, and `VisionExecutor`'s three dispatch tables (`_CAPABILITY_METHOD`, `_CAPABILITY_FACTORY`, `_CAPABILITY_EVENT`) and `VisionRuntime`'s two aggregation tables (`_REGISTRIES`, `_FACTORIES`) were keyed by the raw string literals `"image"`/`"document"`/`"extraction"`/`"analysis"` — even though `VisionCapabilityCategory` (with exactly those four values) already existed in `vision/capabilities/enums.py` and was used elsewhere (capability declarations). The routing code and the taxonomy that was supposed to describe it had drifted apart.

**Fixed** (`vision/request.py`, `vision/context.py`, `vision/execution.py`, `vision/runtime.py`):
- `VisionRequest.capability_category` and `VisionContext.capability_category` are now typed `VisionCapabilityCategory` (`| None` for the context).
- `VisionRequest.__post_init__` normalizes a plain string into the real enum member on construction (e.g. `"image"` → `VisionCapabilityCategory.IMAGE`), silently leaving an unrecognized value as a plain string — `VisionExecutor`'s existing "Unknown capability_category" check still catches that case exactly as it did before; no new validation/failure mode was introduced.
- Every dispatch/aggregation dict is now keyed by the enum member (`VisionCapabilityCategory.IMAGE: "describe"`, etc.) instead of the literal string.

**Why this is a genuine zero-behavior-change fix**: `VisionCapabilityCategory` is a `StrEnum` — its members *are* string instances, equal-in-hash and equal-in-value to the literal strings previously used as dict keys. A test (or any future caller) that still constructs a request with `capability_category="image"` continues to route to exactly the same provider factory and emit exactly the same events, because `VisionCapabilityCategory.IMAGE == "image"` and `hash(VisionCapabilityCategory.IMAGE) == hash("image")`. Verified directly (not just by argument): the existing 137 Vision tests pass unchanged, and a direct smoke test confirms `VisionRequest(capability_category="image")` coerces to the enum, `VisionRequest(capability_category=VisionCapabilityCategory.DOCUMENT)` passes through unchanged, and `VisionRequest(capability_category="bogus")` is left as a plain string and still produces the identical `"Unknown capability_category: 'bogus'"` error it did before.

### Open/Closed, Confirmed Unaffected

Adding a fifth Vision capability category still means adding one enum member plus one entry in each of the five dict tables above — no conditional branch, no `if/elif` chain, exactly the same Open/Closed shape as before this change (see [Vision_Framework.md](../04_CAPABILITIES/Vision_Framework.md)).

## Reviewed, and Deliberately Left Name-Based

### `Dispatcher.dispatch()`'s `decision.selected_agent` override

`agents/executive/dispatcher.py`: when `Decision.selected_agent` is set, `Dispatcher` returns `candidates.get(decision.selected_agent)` — a name lookup, checked *before* capability matching. This is an intentional explicit-override escape hatch ("route to this specific agent, regardless of capability"), not a case where capability routing was skipped or forgotten. Left unchanged.

### `SpecialistDispatcher.dispatch_by_specialization(specialization: str)`

`agents/specialists/dispatcher.py` has two routing methods: `dispatch_by_task_type(SpecialistTaskType)` (capability-based, used by the type system) and `dispatch_by_specialization(str)` (name-based — `specialization` is a free-form label set at registration time, not a closed enum). The latter is exercised only by its own tests today; nothing in production code calls it. It was **not** converted to an enum, for two reasons: `specialization` is documented and tested as a free-form string (e.g. `"research"`, `"finance"`) by design — there is no existing closed enum for "specialist domain names" to reuse (inventing one would violate "reuse existing capability enums, do not introduce new taxonomy"), and this method has no current caller whose behavior could regress or improve either way. Left unchanged; flagged here for visibility, not silently ignored.

### `ExecutiveAgent._handle_task()`'s `kind` dispatch chain

`agents/executive/executive_agent.py`: `_handle_task()` is an `if kind == TASK_KIND_RETRIEVE_MEMORY: ... elif kind == TASK_KIND_BUILD_CONTEXT: ...` chain, where `TASK_KIND_*` are plain string constants (not an enum) identifying the Executive's own five built-in step types. This looks superficially like "name-based routing that should become capability-based," but it is a different thing entirely: these are the Executive's own internal, hardcoded pipeline steps (dispatched to the Executive's *own* private handler methods), not a decision about *which external agent/tool/provider* should handle something. There is no existing capability enum that means "internal executive step kind," and inventing one would violate "reuse existing enums" while changing internal control flow the task explicitly asks to leave alone. **Not converted** — this is the Executive's own procedure, not a capability-routing decision.

### Vision and Conversation provider *selection* (vendor, not capability)

`ImageVisionProviderFactory.create(request.provider, config)` and `ConversationProviderFactory.create(provider_name, config)` both resolve a provider by `ProviderName` — i.e., by the specific vendor the caller named, never by "any provider that declares capability X." This is name/identity-based by design, platform-wide, and consistent: a request always says which vendor to use; the framework never auto-selects among multiple registered vendors based on declared capability. Changing this to capability-driven vendor auto-selection (e.g., "pick any registered image provider that supports `ImageCapability.CAPTIONING`") would be a new feature — a real behavior and API change — not a routing fix, and is explicitly out of scope for this pass. Left unchanged.

### `AgentRegistry.get(name)` / `SpecialistRegistry.get(name)` / `ToolRegistry.get(tool_id)`

All three registries resolve by identity (agent name, specialist name, tool id), not capability. This is correct and was not changed: a registry's job is "give me the specific thing registered under this identity," which is a different question from "what can handle this need" (already answered separately and correctly by `AgentCapability`/`SpecialistTaskType`/`ToolCapability` lookups on the same registrations — see `ToolDiscovery.by_capability()`, `SpecialistDispatcher.dispatch_by_task_type()`).

## Deliberately Not Wired: the Platform-Wide `Capability` Enum

`app/services/ai/capabilities/enums.py`'s `Capability` (`CONVERSATION`, `EMBEDDING`, `REASONING`, `VISION`, `SPEECH`, `IMAGE_GENERATION`, `RERANKING`, `PLANNING`, `TOOL_CALLING`) remains unused by any production code, exactly as it was before this pass (see [Package_Architecture.md](Package_Architecture.md)). It was considered as a candidate for "the universal dispatch language" but not wired into anything: there is no current name-based routing anywhere in the platform that this specific enum is the natural replacement for — `AgentCapability`, `ToolCapability`, `SpecialistTaskType`, and `VisionCapabilityCategory` already cover every real routing decision that exists today, each scoped to its own subsystem. Forcibly wiring `Capability` into one of them now would mean either duplicating an existing, correctly-scoped enum, or introducing a new cross-cutting routing layer nothing currently needs — both against this pass's "no behavior change, reuse existing enums" constraint. This remains open, documented work for whenever a routing decision actually needs to span multiple capability frameworks at once (e.g., "does this organization have *any* capability that can do X, across Conversation, Vision, and Tools simultaneously").

## Every Subsystem Now Using Capability-Based Routing

| Subsystem | Capability enum | Routing mechanism |
|---|---|---|
| Executive → Agent delegation | `AgentCapability` | `Dispatcher.dispatch()` matches `task.metadata["required_capability"]` against `agent.capabilities().declared` |
| Specialist lookup | `SpecialistTaskType` | `SpecialistDispatcher.dispatch_by_task_type()` matches against `SpecialistRegistry`'s registration-time `supported_tasks` |
| Tool discovery | `ToolCapability`, `ToolPermission`, `ToolCategory` | `ToolDiscovery.by_capability()`/`by_permission()`/`by_category()` against `ToolRegistry`'s registration-time metadata |
| Vision execution | `VisionCapabilityCategory` | **(new, M20.4)** `VisionExecutor`'s `_CAPABILITY_METHOD`/`_CAPABILITY_FACTORY`/`_CAPABILITY_EVENT` and `VisionRuntime`'s `_REGISTRIES`/`_FACTORIES`, all keyed by the enum |

Every one of these preserves Open/Closed: adding a new agent, specialist, tool, or Vision capability category never requires modifying the dispatch mechanism itself, only registering the new entry with accurate capability metadata.
