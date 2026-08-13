# Package Architecture

A package-by-package reference for the AI Operating System and the intelligence-layer packages it depends on. Each entry lists purpose, responsibilities, dependencies (internal only — stdlib is omitted), and public API surface. Packages are grouped by layer, matching [System_Architecture.md](System_Architecture.md).

---

## Shared Infrastructure

### `app/services/ai/shared/`

**Purpose**: Platform-wide primitives every other package composes rather than redefines.

**Responsibilities**: Execution identity (`SharedExecutionContext`, `ExecutionMetadata`), the canonical registry/event/middleware generics (`GenericProviderRegistry`, `GenericEvent`/`EventPublisher`, `GenericMiddleware`/`GenericMiddlewarePipeline`), provider-neutral config/metadata (`BaseProviderConfig`, `ProviderMetadata`), the generic provider-construction helper (`BaseProviderFactory`), normalized response building blocks (`ProviderResponse`, `UsageDetails`, `FinishReason`), and the platform's root exceptions (`AIProviderError`, `AIRuntimeError`'s sibling in this package).

**Dependencies**: `providers/` only (`ProviderResponse` needs `ProviderName`) — otherwise the leaf package every other AI-OS package may depend on.

**Public API**: `SharedExecutionContext`, `ExecutionMetadata`, `GenericProviderRegistry[TKey, TValue]`, `GenericEvent`, `EventPublisher[TEvent]`, `hash_event()`, `GenericMiddleware`, `GenericMiddlewarePipeline`, `BaseProviderConfig`, `ConversationProviderConfig`, `ProviderMetadata`, `BaseProviderFactory[TProvider, TConfig]`, `ProviderResponse`, `UsageDetails`, `FinishReason`, `AIProviderError`. Full detail: [Shared_Infrastructure.md](Shared_Infrastructure.md).

### `app/services/ai/providers/`

**Purpose**: The one platform-wide vendor taxonomy.

**Responsibilities**: `ProviderName` (StrEnum: `OPENAI`, `ANTHROPIC`, `GEMINI`, `OLLAMA`, `OPENROUTER`, `DEEPSEEK`, `QWEN`, `MISTRAL`, `GROK`, `UNKNOWN`). Every registry keyed by provider identity (`ConversationProviderRegistry`, all four Vision registries) uses this same enum — `app.services.ai.vision.providers.enums` re-exports it rather than redeclaring it.

**Dependencies**: None.

**Public API**: `ProviderName`.

### `app/services/ai/capabilities/`

**Purpose**: A declared, platform-wide capability taxonomy.

**Responsibilities**: `Capability` (StrEnum: `CONVERSATION`, `EMBEDDING`, `REASONING`, `VISION`, `SPEECH`, `IMAGE_GENERATION`, `RERANKING`, `PLANNING`, `TOOL_CALLING`).

**Dependencies**: None.

**Public API**: `Capability`. **Note**: as of M19 this enum is not imported by any production code — it is exercised only by its own test file. It documents an intended future taxonomy (most capabilities listed have no framework built yet) rather than a wired-in mechanism. Do not confuse this with `AgentCapability` (`agents/capabilities.py`) or `ToolCapability` (`tools/enums.py`), which are separate, actually-used enums scoped to their own frameworks.

---

## Kernel

### `app/services/ai/kernel/`

**Purpose**: The AI Operating System's foundational, capability-agnostic execution contracts.

**Responsibilities**: Declares (but as of M19 mostly does not yet implement) the kernel-level execution model: `ExecutionContext`, `ExecutionRequest`/`ExecutionResponse`, `KernelRuntime`, `RuntimeRegistry`/`RuntimePipeline`, `KernelMiddleware`/`KernelHook` contracts, `RetryPolicy`/`BackoffStrategy`, cancellation/timeout contracts, `ExecutionMetrics`/`TokenUsageReference`/`CostEstimate`, `ExecutionState`, `ExecutionMode` scheduling enum, `ExecutionGraph`, `ModelIdentity`, and the kernel's own root `KernelError`.

**Dependencies**: Deliberately **none** within `app.services.ai`, with exactly one sanctioned exception: `kernel/context.py` composes `app.services.ai.shared.execution_context.SharedExecutionContext`. Every other kernel module (including its own `Metadata`/`Payload` aliases in `types.py`) depends on nothing outside the kernel — see [Dependency_Rules.md](Dependency_Rules.md).

**Public API**: `KernelRuntime`, `ExecutionContext`, `ExecutionRequest`/`ExecutionResponse`, `RuntimeRegistry`, `RuntimePipeline`, `KernelMiddleware`, `KernelHook`, `RetryPolicy`, `ExecutionMetrics`, `ExecutionState`, `ExecutionMode`, `KernelError`. Full detail, including exactly what is and isn't implemented: [Kernel.md](../02_KERNEL/Kernel.md).

---

## Runtime & Conversation

### `app/services/ai/runtime/`

**Purpose**: The concrete, working execution engine for the Conversation capability.

**Responsibilities**: `AIRuntime` (public facade), `RuntimeExecutor` (retry/timeout/cancellation/middleware/event orchestration), `RuntimeContext`/`RuntimeRequest`/`RuntimeResponse`/`RuntimeExecutionResult`, `RuntimeMiddleware`/`MiddlewarePipeline`, `RuntimeHook`, `RuntimeEvent`/`RuntimeEventPublisher`/`EventType`, `CancellationToken`, `RuntimeTimeout`/`RuntimeTimeoutError`.

**Dependencies**: `shared/` (identity, generic events/middleware, exceptions), `conversation/` (`ConversationProviderFactory`, `ConversationProvider`, `ConversationResponse`), `providers/` (`ProviderName`), `prompt_builder/` (`PromptPackage`, the input type).

**Public API**: `AIRuntime`, `RuntimeExecutor`, `RuntimeRequest`, `RuntimeResponse`, `RuntimeMiddleware`, `MiddlewarePipeline`, `RuntimeHook`, `RuntimeEvent`, `RuntimeEventPublisher`, `EventType`, `CancellationToken`, `RuntimeTimeout`, `RuntimeTimeoutError`. Full detail: [Runtime.md](../02_KERNEL/Runtime.md).

### `app/services/ai/conversation/`

**Purpose**: The Conversation capability's provider contract and resolution mechanism.

**Responsibilities**: `ConversationProvider` ABC, `ConversationResponse`/`ConversationStreamChunk`, `ConversationProviderRegistry`, `ConversationProviderFactory`.

**Dependencies**: `shared/` (`GenericProviderRegistry`, `BaseProviderFactory`, `AIProviderError`, `ProviderResponse`/`UsageDetails`/`FinishReason`), `providers/` (`ProviderName`), `prompt_builder/` (`PromptPackage`).

**Public API**: `ConversationProvider`, `ConversationResponse`, `ConversationStreamChunk`, `ConversationProviderRegistry`, `ConversationProviderFactory`. Full detail: [Conversation_Framework.md](../04_CAPABILITIES/Conversation_Framework.md).

---

## Agent Framework

### `app/services/ai/agents/`

**Purpose**: The general-purpose agent contract and lifecycle machinery every concrete agent (Executive, specialists) builds on.

**Responsibilities**: `BaseAgent` ABC (fully abstract), `AgentContext` (composes `SharedExecutionContext`), `AgentIdentity`, `AgentCapabilities`/`AgentCapability`, `AgentState`/`AgentStateMachine`, `AgentRegistry`, `AgentFactory`, `AgentExecutor`, `AgentEvent`/`AgentEventPublisher`/`AgentEventType`, `AgentPlanner` ABC (unimplemented contract), `AgentMemory` ABC (unimplemented contract — see [Memory_System.md](../03_INTELLIGENCE/Memory_System.md)), policies (`PermissionPolicy`/`ExecutionPolicy`/`TimeoutPolicy`, re-exporting kernel's `RetryPolicy`), `messages.py`, `orchestrator.py` (`AgentOrchestrator` ABC).

**Dependencies**: `shared/` (identity, generics), `kernel/` (`RetryPolicy`, `ExecutionMetrics`, `TokenUsageReference` — explicitly allowed), `runtime/` (`RuntimeResponse`, reused by `AgentExecutionResult`).

**Public API**: `BaseAgent`, `AgentContext`, `AgentIdentity`, `AgentCapabilities`, `AgentState`, `AgentRegistry`, `AgentFactory`, `AgentExecutor`, `AgentEvent`, `AgentEventPublisher`, `AgentPlanner`, `AgentMemory`, `PermissionPolicy`, `ExecutionPolicy`, `TimeoutPolicy`.

### `app/services/ai/agents/executive/`

**Purpose**: The Executive agent — the platform's top-level planner/delegator ("PID 1").

**Responsibilities**: `ExecutiveAgent`, `ExecutivePlanner`, `Dispatcher`, `Decision`, `Task`/`TaskGraph`/`TaskResult`, `ExecutivePolicy`, `ExecutiveState`/`ExecutiveStateMachine`, `ExecutiveEvent`/`ExecutiveEventPublisher`, `ExecutiveContext`.

**Dependencies**: `agents/` (`BaseAgent`, `AgentContext`, ...), `agents/specialists/` (`SpecialistRegistry`/`Dispatcher`, for delegation), `shared/`, `kernel/` (`RetryPolicy`), `runtime/` and `providers/` (`ExecutiveAgent` calls `AIRuntime` directly for its own conversational capability, not only delegation).

**Public API**: `ExecutiveAgent`, `ExecutivePlanner`, `Dispatcher`, `Task`, `TaskGraph`, `ExecutiveEvent`. Full detail: [Executive_Agent.md](../05_AGENTS/Executive_Agent.md), [Executive_Framework.md](../03_INTELLIGENCE/Executive_Framework.md).

### `app/services/ai/agents/specialists/`

**Purpose**: The Specialist agent framework — the extension point for adding new specialist agents (Research today; Learning/Product/Finance on the roadmap).

**Responsibilities**: `specialist_agent.py` (`SpecialistAgent` ABC), `shared/` (`SpecialistTask`/`Request`/`Response`/`Result`/`ExecutionPolicy`/`Context`, `aggregate_metrics`), `planner.py` (`SpecialistPlanner`), `memory_adapter.py`/`tool_adapter.py`/`runtime_adapter.py` (thin delegating wrappers), `registry.py` (`SpecialistRegistry`, recording `specialization`/`supported_tasks` at registration time), `dispatcher.py` (`SpecialistDispatcher`), `factory.py` (`SpecialistFactory`), `coordinator.py` (`SpecialistCoordinator`, a plain DI container).

**Dependencies**: `agents/` (`BaseAgent`, `AgentPlanner`), `tools/` (via `ToolAdapter`), `runtime/` (via `RuntimeAdapter`), `retrieval/` (via `MemoryAdapter` → `MemoryRetrievalPipeline`), `shared/`, `kernel/` (`RetryPolicy`).

**Public API**: `SpecialistAgent`, `SpecialistRegistry`, `SpecialistDispatcher`, `SpecialistFactory`, `SpecialistCoordinator`, `SpecialistExecutionPolicy`. Full detail: [Specialist_Framework.md](../03_INTELLIGENCE/Specialist_Framework.md).

### `app/services/ai/agents/specialists/research/`

**Purpose**: The first concrete specialist — a research/investigation agent.

**Responsibilities**: `ResearchAgent`, `ResearchPlanner`, `ResearchState`/`StateMachine`, `ResearchEvent`/`ResearchEventPublisher`, `ResearchPolicy`, `ResearchReport`, `ResearchSynthesizer`, `context.py`.

**Dependencies**: `agents/specialists/` (`SpecialistAgent`, adapters, shared value objects), `tools/` (via `ToolAdapter`, to invoke real tools), `shared/`, `runtime/`, `kernel/` (`ExecutionMetrics`), `providers/` — like `ExecutiveAgent`, `ResearchAgent` calls `AIRuntime` directly (its `RuntimeAdapter` wraps the call, not the `RuntimeRequest`/`RuntimeResponse` value objects it still constructs and reads).

**Public API**: `ResearchAgent`, `ResearchReport`. Full detail: [Research_Agent.md](../05_AGENTS/Research_Agent.md).

---

## Tool Framework

### `app/services/ai/tools/`

**Purpose**: The universal contract and execution engine for giving agents tool access.

**Responsibilities**: `BaseTool` ABC (abstract + concrete `manifest()`), `ToolContext` (composes `SharedExecutionContext` + `CancellationToken`), `ToolResult` (composes `ExecutionMetrics`), `ToolRegistry`/`ToolFactory`, `ToolManager`, `ToolExecutor`, `ToolMiddleware`/`ToolMiddlewarePipeline`, `ToolHook`, `PermissionPolicy`/`ToolExecutionPolicy` (reusing `RetryPolicy`), `ToolDiscovery`, `validation.py`, `schema.py` (`ToolSchema`/`SchemaField`, pure Python).

**Dependencies**: `shared/` (identity, `GenericProviderRegistry`, `GenericEvent`, `GenericMiddleware`), `runtime/` (`CancellationToken`, `RuntimeTimeout`), `kernel/` (`RetryPolicy`).

**Public API**: `BaseTool`, `ToolContext`, `ToolResult`, `ToolRegistry`, `ToolFactory`, `ToolManager`, `ToolExecutor`, `ToolMiddleware`, `ToolMiddlewarePipeline`, `ToolHook`, `ToolExecutionPolicy`, `ToolSchema`. Full detail: [Tool_Framework.md](../04_CAPABILITIES/Tool_Framework.md).

### `app/services/ai/tools/shared/`

**Purpose**: Tool-Framework-local leaf types.

**Responsibilities**: `Metadata` alias, `ToolError`/`ToolNotFoundError` and sibling exceptions.

**Dependencies**: None (deliberately, mirroring the Kernel's own leaf-module convention — see [Philosophy.md](../00_OVERVIEW/Philosophy.md)).

**Public API**: `Metadata`, `ToolError`, `ToolNotFoundError`.

---

## Vision Framework

### `app/services/ai/vision/`

**Purpose**: A shared OS capability (not an agent) for image, document, extraction, and analysis understanding — usable by any current or future agent.

**Responsibilities**: `VisionRuntime`, `VisionExecutor`, `VisionRequest`/`VisionResponse`/`VisionContext`, `VisionMiddleware`/`VisionMiddlewarePipeline`, `VisionHook`, `VisionEvent`/`VisionEventPublisher`/`VisionEventType`, plus four independent capability sub-packages (below).

**Dependencies**: `shared/` (identity, all three generics), `runtime/` (`CancellationToken`, `RuntimeTimeout` — reused, not duplicated), `kernel/` (`ExecutionMetrics`), `providers/` (`ProviderName`, re-exported by `vision/providers/enums.py`).

**Public API**: `VisionRuntime`, `VisionExecutor`, `VisionRequest`, `VisionResponse`, `VisionEvent`, `VisionEventPublisher`. Full detail: [Vision_Framework.md](../04_CAPABILITIES/Vision_Framework.md).

### `app/services/ai/vision/shared/`

**Purpose**: Vision-Framework-wide value objects and the base provider contract.

**Responsibilities**: `types.py` (`BoundingBox`, `DetectedObject`, `ExtractedText`, `ExtractedTable`, `VisionCapabilities`, `ImageMetadata`, `DocumentMetadata`, `VisionMetadata`, `Metadata`), `exceptions.py` (`VisionError`, `VisionProviderError`, `VisionExecutionError`), `base_provider.py` (`BaseVisionProvider` ABC).

**Dependencies**: `shared/` (`ProviderMetadata`), `providers/` (`ProviderName`).

### `app/services/ai/vision/{image,document,extraction,analysis}/`

**Purpose**: Four independent capability services, each following the identical pattern.

**Responsibilities** (per capability): `base_provider.py` (one capability ABC — `ImageVisionProvider.describe()`, `DocumentVisionProvider.understand()`, `ExtractionProvider.extract()`, `AnalysisProvider.analyze()`), `registry.py` (`{Capability}ProviderRegistry`, extending `GenericProviderRegistry`), `provider_factory.py` (`{Capability}ProviderFactory`, extending `BaseProviderFactory`).

**Dependencies**: `vision/shared/`, `vision/providers/`, `shared/` (`GenericProviderRegistry`, `BaseProviderFactory`, `BaseProviderConfig`).

**Public API**: `ImageVisionProvider`/`ImageVisionProviderRegistry`/`ImageVisionProviderFactory` (and the analogous three sets).

### `app/services/ai/vision/providers/` and `app/services/ai/vision/capabilities/`

**Purpose**: `providers/enums.py` re-exports the platform's `ProviderName` (does not redeclare it — `assert ProviderName is PlatformProviderName` is enforced by test). `capabilities/enums.py` declares `VisionCapabilityCategory` and the four per-capability enums (`ImageCapability`, `DocumentCapability`, `ExtractionCapability`, `AnalysisCapability`).

---

## Intelligence Layer (outside `app/services/ai/`)

### `app/services/prompt_builder/`

**Purpose**: Deterministic assembly of a `PromptPackage` from a query, retrieved context, and conversation history.

**Responsibilities**: `types.py` (`PromptMessage`, `PromptSection`, `PromptPackage`), `builder.py` (`PromptBuilder`), `sections.py` (section-building functions), `templates.py` (string constants), `renderers.py` (`render_messages`/`render_text`).

**Dependencies**: `app/services/context/` (`ContextPackage`, the input type). No LLM, DB, ranking, or embedding dependency — a pure, deterministic transform.

**Public API**: `PromptBuilder`, `PromptPackage`, `PromptMessage`, `PromptSection`. Full detail: [Prompt_Builder.md](../03_INTELLIGENCE/Prompt_Builder.md).

### `app/services/context/`

**Purpose**: Turns ranked retrieval results into a token-budgeted, grouped `ContextPackage`.

**Responsibilities**: `context_builder.py` (`ContextBuilder`), `pipeline.py` (`ContextPipeline`, a generic stage runner), `types.py` (`RankedResult` Protocol, `ContextItem`, `ContextSection`, `ContextPackage`), `stages/` (`DuplicateStage`, `BudgetStage`, `GroupingStage`, `FormatterStage`, each a `PipelineStage`).

**Dependencies**: None on ranking/embedding/DB — deliberately decoupled; consumes anything structurally matching the `RankedResult` Protocol.

**Public API**: `ContextBuilder`, `ContextPackage`.

### `app/services/retrieval/`

**Purpose**: The single integration point tying semantic search, ranking, and context building together.

**Responsibilities**: `memory_retrieval_pipeline.py` (`MemoryRetrievalPipeline`), `adapters.py` (pure conversion functions between `SemanticSearchResult` → `RankingCandidate`/`RankedCandidate` → `RetrievalResult`), `types.py` (`RetrievalResult`).

**Dependencies**: `app/services/semantic_search_service.py`, `app/services/ranking/`, `app/services/context/`.

**Public API**: `MemoryRetrievalPipeline`. Full detail: [Retrieval.md](../03_INTELLIGENCE/Retrieval.md).

### `app/services/ranking/`

**Purpose**: Scores and orders retrieval candidates.

**Responsibilities**: `base_strategy.py` (`RankingStrategy` ABC), `default_strategy.py` (`DefaultRankingStrategy`, similarity + recency blend), `ranking_engine.py` (`RankingEngine`), `types.py` (`RankingCandidate`, `RankedCandidate`).

**Dependencies**: None — purely in-memory, no DB coupling.

### `app/services/embedding/` and `app/services/vector_store/`

**Purpose**: Text-to-vector generation and vector persistence/search, the foundation the semantic-search layer is built on.

**Responsibilities**: `embedding/` — `EmbeddingProvider` ABC, `OpenAIEmbeddingProvider`, `EmbeddingProviderRegistry`, `EmbeddingProviderFactory`. `vector_store/` — `VectorStore` ABC, `NullVectorStore`, `PgVectorStore`, `VectorStoreRegistry`, `VectorStoreFactory`, `VectorId`, `VectorMetadata`.

**Dependencies**: As of M20.5, both registries (`EmbeddingProviderRegistry`, `VectorStoreRegistry`) extend `app.services.ai.shared.provider_registry.GenericProviderRegistry` directly — no longer a structurally-similar-but-independent hand-rolled dict. See [Dependency_Rules.md](Dependency_Rules.md) for the resulting cross-boundary dependency this introduces.

**Also in this layer**: `app/services/embedding_service.py` (`EmbeddingService` — text-to-vector only, no storage) and `app/services/embedding_persistence_service.py` (`EmbeddingPersistenceService` — the one place that combines `EmbeddingService` and a `VectorStore`; used independently by `AIMemoryService` and `ConversationMessageService`, below). See [Memory_Layer_Rationalization.md](../03_INTELLIGENCE/Memory_Layer_Rationalization.md) §1 ("Vector Memory").

### `app/services/ai_memory_service.py`, `app/services/memory_service.py`, `app/services/semantic_search_service.py`

**Purpose**: Two distinct memory layers plus the semantic search service that bridges them to retrieval. See [Memory_System.md](../03_INTELLIGENCE/Memory_System.md) for the full, important distinction between `AIMemoryService`/`Memory` (content + embeddings) and `MemoryService`/`MemoryRecord` (key/value notes, no embedding pipeline).

**Dependencies**: `app/repositories/`, `app/models/`, `embedding/`, `vector_store/`.

### `app/services/conversation_service.py`, `app/services/conversation_message_service.py`

**Purpose**: Persisted chat history — "Conversation Memory," entirely unrelated to `app/services/ai/conversation/` (the AI-OS's provider-agnostic LLM contract, see [Conversation_Framework.md](../04_CAPABILITIES/Conversation_Framework.md)) despite the shared name. See [Memory_Layer_Rationalization.md](../03_INTELLIGENCE/Memory_Layer_Rationalization.md) §5.

**Responsibilities**: `ConversationService` (create/get/list/list_active/archive/delete a `Conversation`), `ConversationMessageService` (add/get/list `ConversationMessage` rows, plus best-effort embedding persistence on write — independently duplicating the same graceful-degradation pattern `AIMemoryService` uses, flagged as a real merge candidate in the rationalization doc above).

**Dependencies**: `app/repositories/` (`ConversationRepository`, `ConversationMessageRepository`), `app/models/` (`Conversation`, `ConversationMessage`), `embedding_persistence_service.py`.

**Public API**: `ConversationService`, `ConversationMessageService`. Routed via `app/api/v1/routes/conversations.py` and `conversation_messages.py`.
