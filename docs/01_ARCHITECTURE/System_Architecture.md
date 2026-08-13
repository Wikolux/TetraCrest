# System Architecture

This is the blueprint for the AI Operating System (`app/services/ai/`) as it exists after M19. It describes the layers, how they compose, and how a request actually flows through the system today — as opposed to what is architected-but-not-yet-implemented (the Kernel; see the callout below) or roadmap (see [Roadmap.md](../00_OVERVIEW/Roadmap.md)).

## Layered Architecture

```mermaid
flowchart TB
    subgraph L5["Agents"]
        Executive["Executive Agent (M17)"]
        Research["Research Specialist (M18)"]
        FutureSpec["Future Specialists (Learning, Product, Finance...)"]
    end

    subgraph L4["Agent Framework (M16)"]
        BaseAgent["BaseAgent / AgentContext / AgentRegistry / AgentExecutor"]
    end

    subgraph L3["Capability Frameworks"]
        Conversation["Conversation Framework"]
        Vision["Vision Framework (M19)"]
        Tools["Tool Framework (M17)"]
    end

    subgraph L2["Runtime"]
        AIRuntime["AIRuntime / RuntimeExecutor"]
    end

    subgraph L1["Kernel (architecture only, see Kernel.md)"]
        KernelRuntime["KernelRuntime / ExecutionContext"]
    end

    subgraph L0["Shared Infrastructure"]
        Shared["SharedExecutionContext, GenericProviderRegistry,\nGenericEvent/Publisher, GenericMiddleware/Pipeline,\nRetryPolicy, ExecutionMetrics"]
    end

    L5 --> L4
    L4 --> L3
    L3 --> L2
    L2 -.declared contract, not yet composed.-> L1
    L3 --> L0
    L4 --> L0
    L5 --> L0
    L1 --> L0
```

**Read this diagram carefully**: the Kernel (L1) is drawn separately because, as of M19, it is a fully-specified but largely unimplemented contract layer — `KernelRuntime.execute()` validates its input and then raises `NotImplementedError`. The Runtime (L2) does **not** currently sit on top of the Kernel; it is a separate, working execution engine that was built to replace an earlier capability-agnostic draft engine, and is provider-coupled (conversation-specific) by design. Every other layer depends on Shared Infrastructure (L0) directly. See [Kernel.md](../02_KERNEL/Kernel.md) for the full accounting of what the Kernel actually implements today.

## Component Diagram

```mermaid
flowchart LR
    subgraph Agents
        EA[ExecutiveAgent]
        RA[ResearchAgent]
    end

    subgraph AgentFramework["Agent Framework"]
        AR[AgentRegistry]
        AF[AgentFactory]
        AX[AgentExecutor]
    end

    subgraph Capabilities
        direction TB
        CV[Conversation Framework]
        VI[Vision Framework]
        TL[Tool Framework]
    end

    subgraph Runtime
        RT[AIRuntime]
        RX[RuntimeExecutor]
    end

    subgraph Shared["Shared Infrastructure"]
        SEC[SharedExecutionContext]
        GPR[GenericProviderRegistry]
        GE[GenericEvent / EventPublisher]
        GM[GenericMiddleware / Pipeline]
        RP[RetryPolicy]
        EM[ExecutionMetrics]
    end

    EA -->|delegates via Dispatcher| RA
    EA --> AX
    RA --> AX
    AX --> AR
    AX --> AF
    EA --> TL
    RA --> TL
    EA --> CV
    RA --> VI
    CV --> RT
    RT --> RX
    RX --> GPR
    TL --> GPR
    VI --> GPR
    CV --> GE
    TL --> GE
    VI --> GE
    RX --> GM
    TL --> GM
    VI --> GM
    EA --> SEC
    RA --> SEC
    RX --> SEC
    TL --> SEC
    VI --> SEC
    RX --> RP
    TL --> RP
    VI --> RP
    RX --> EM
```

## Capability Hierarchy

> See [Capability_Routing.md](Capability_Routing.md) for how capability enums (`AgentCapability`, `ToolCapability`, `SpecialistTaskType`, `VisionCapabilityCategory`) drive dispatch platform-wide, and where routing is intentionally identity-based instead.

Every capability framework — Conversation, Vision, and (structurally) Tools — follows the same shape, deliberately:

```
Agent → Capability Framework → Provider (abstract contract) → Provider Implementation (vendor-specific)
```

| Capability | Framework package | Provider ABC(s) | Providers registered today |
|---|---|---|---|
| Conversation | `app/services/ai/conversation/` | `ConversationProvider` | None — architecture only |
| Vision — Image | `app/services/ai/vision/image/` | `ImageVisionProvider` | None — architecture only |
| Vision — Document | `app/services/ai/vision/document/` | `DocumentVisionProvider` | None — architecture only |
| Vision — Extraction | `app/services/ai/vision/extraction/` | `ExtractionProvider` | None — architecture only |
| Vision — Analysis | `app/services/ai/vision/analysis/` | `AnalysisProvider` | None — architecture only |
| Tools | `app/services/ai/tools/` | `BaseTool` (tools self-register directly, no separate provider layer) | None built-in yet |

No concrete, vendor-specific provider exists anywhere in this platform as of M19 — every capability is exercised in tests via hand-written fakes implementing the real ABCs. This is intentional: the frameworks are proven provider-agnostic by construction, not by convention.

## Agent Hierarchy

```mermaid
classDiagram
    class BaseAgent {
        <<ABC>>
        +initialize()
        +execute()
        +pause()
        +resume()
        +cancel()
        +shutdown()
        +health()
        +capabilities()
        +permissions()
        +memory()
        +planner()
        +runtime()
    }
    class SpecialistAgent {
        <<ABC>>
    }
    class ExecutiveAgent
    class ResearchAgent

    BaseAgent <|-- ExecutiveAgent
    BaseAgent <|-- SpecialistAgent
    SpecialistAgent <|-- ResearchAgent
```

`ExecutiveAgent` self-registers in `AgentRegistry` under the name `"executive"`; `ResearchAgent` self-registers under `SpecialistRegistry` (a distinct, specialist-scoped registry that additionally records `specialization`/`supported_tasks` at registration time — see [Specialist_Framework.md](../03_INTELLIGENCE/Specialist_Framework.md)). Both are still full `BaseAgent`s and are also discoverable through `AgentRegistry`.

## Request Lifecycle (Conversation, the fully-implemented path)

```mermaid
sequenceDiagram
    participant Caller
    participant Runtime as AIRuntime
    participant Exec as RuntimeExecutor
    participant MW as MiddlewarePipeline
    participant Factory as ConversationProviderFactory
    participant Provider

    Caller->>Runtime: execute(RuntimeRequest)
    Runtime->>Exec: execute(request)
    Exec->>Exec: build SharedExecutionContext (child of parent_shared, if any)
    Exec-->>Caller: emit EventType.STARTED
    Exec->>Exec: before_execution hooks
    loop retry loop (max_retries + 1 attempts)
        Exec->>MW: run(context, request, handler)
        MW->>Factory: create(provider_name, config)
        Factory-->>MW: Provider instance (or raises AIProviderError, not retried)
        MW->>Provider: generate(prompt_package), wrapped in RuntimeTimeout
        Provider-->>MW: ConversationResponse (or raises / times out)
        Exec-->>Caller: emit PROVIDER_SELECTED, REQUEST_SENT, RESPONSE_RECEIVED
    end
    Exec-->>Caller: emit COMPLETED or FAILED
    Exec->>Exec: after_execution hooks
    Exec-->>Runtime: RuntimeResponse (success/error, identity, metrics)
    Runtime-->>Caller: RuntimeResponse
```

This same shape (executor → middleware pipeline → factory-resolved provider → structured response, never a raised exception) is repeated, with capability-specific types, by `ToolExecutor` and `VisionExecutor`. See [Runtime.md](../02_KERNEL/Runtime.md), [Tool_Framework.md](../04_CAPABILITIES/Tool_Framework.md), and [Vision_Framework.md](../04_CAPABILITIES/Vision_Framework.md).

## Data Flow: Retrieval → Context → Prompt → Execution

This is the path a user query actually takes to become a grounded LLM call, spanning the Intelligence layer and the Runtime:

```mermaid
flowchart LR
    Q[User query] --> SS[SemanticSearchService]
    SS -->|SemanticSearchResult list| AD1["adapters.semantic_results_to_ranking_candidates"]
    AD1 --> RE[RankingEngine]
    RE -->|RankedCandidate list| AD2["adapters.ranking_results_to_context_results"]
    AD2 -->|RetrievalResult list| CB[ContextBuilder pipeline]
    CB -->|ContextPackage| PB[PromptBuilder]
    PB -->|PromptPackage| RT[AIRuntime / RuntimeExecutor]
    RT --> PR[ConversationProvider]
```

The `MemoryRetrievalPipeline` (`app/services/retrieval/`) is the single orchestration point tying `SemanticSearchService`, `RankingEngine`, and `ContextBuilder` together; `ContextBuilder` and `RankingEngine` never import each other directly — the adapters in `app/services/retrieval/adapters.py` are the only glue. See [Retrieval.md](../03_INTELLIGENCE/Retrieval.md) and [Prompt_Builder.md](../03_INTELLIGENCE/Prompt_Builder.md).

## Shared Infrastructure at a Glance

Every subsystem above composes rather than redefines:

- **Identity**: `SharedExecutionContext` (execution/correlation/causation/parent tracking) — see [Execution_Context.md](../02_KERNEL/Execution_Context.md).
- **Registries**: `GenericProviderRegistry` — see [Shared_Infrastructure.md](Shared_Infrastructure.md).
- **Events**: `GenericEvent`/`EventPublisher` — see [Event_System.md](../02_KERNEL/Event_System.md).
- **Middleware**: `GenericMiddleware`/`GenericMiddlewarePipeline` — see [Middleware.md](../02_KERNEL/Middleware.md).
- **Retry**: `kernel.retry.RetryPolicy`, reused (never redefined) by Tool/Specialist/Vision execution policies.
- **Metrics**: `kernel.metrics.ExecutionMetrics`, composed by `VisionResponse` and others.

Full detail in [Shared_Infrastructure.md](Shared_Infrastructure.md).

## Package-Level Detail

For a package-by-package breakdown (purpose, responsibilities, dependencies, public API) see [Package_Architecture.md](Package_Architecture.md). For which packages may depend on which, see [Dependency_Rules.md](Dependency_Rules.md).
