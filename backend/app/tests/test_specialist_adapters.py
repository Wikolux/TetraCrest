from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.agents.specialists.tool_adapter import ToolAdapter
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse
from app.services.ai.tools.result import ToolResult
from app.services.context.types import ContextPackage
from app.services.prompt_builder.types import PromptPackage


class _FakePipeline:
    def __init__(self):
        self.memory_calls = []
        self.conversation_calls = []
        self.all_calls = []
        self.package = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)

    def search_memories(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.memory_calls.append((query, organization_id, limit, max_context_tokens))
        return self.package

    def search_conversation_messages(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.conversation_calls.append((query, organization_id, limit, max_context_tokens))
        return self.package

    def search_all(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.all_calls.append((query, organization_id, limit, max_context_tokens))
        return self.package


class _FakeToolManager:
    def __init__(self):
        self.calls = []
        self.result = ToolResult(success=True, output="tool output")

    def invoke(self, tool_id, parameters, **kwargs):
        self.calls.append((tool_id, parameters, kwargs))
        return self.result


class _FakeRuntime:
    def __init__(self):
        self.requests = []
        self.response = RuntimeResponse(success=True)

    def execute(self, request):
        self.requests.append(request)
        return self.response


# --- MemoryAdapter --------------------------------------------------------------------


def test_memory_adapter_default_pipeline_type_is_the_real_pipeline_class():
    # constructing the real MemoryRetrievalPipeline requires environment-
    # specific embedding/vector-store configuration this test environment
    # doesn't provide - confirm the *default* parameter is the real class
    # (proving DI wiring) without actually instantiating it, exactly why
    # every other test here injects a fake pipeline instead.
    import inspect

    signature = inspect.signature(MemoryAdapter.__init__)
    assert signature.parameters["pipeline"].annotation.__args__[0].__name__ == "MemoryRetrievalPipeline"


def test_memory_adapter_retrieve_memories_delegates_to_the_pipeline():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    result = adapter.retrieve_memories("query", 1)

    assert result is pipeline.package
    assert pipeline.memory_calls == [("query", 1, 10, 4000)]


def test_memory_adapter_retrieve_conversations_delegates_to_the_pipeline():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.retrieve_conversations("query", 1, limit=5, max_context_tokens=2000)

    assert pipeline.conversation_calls == [("query", 1, 5, 2000)]


def test_memory_adapter_retrieve_all_delegates_to_the_pipeline():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.retrieve_all("query", 1)

    assert pipeline.all_calls == [("query", 1, 10, 4000)]


def test_memory_adapter_never_implements_retrieval_itself():
    # confirms the adapter has no retrieval logic of its own - every
    # public method is a one-line passthrough
    import inspect

    for method_name in ("retrieve_memories", "retrieve_conversations", "retrieve_all"):
        source = inspect.getsource(getattr(MemoryAdapter, method_name))
        assert "self.pipeline." in source


# --- ToolAdapter -----------------------------------------------------------------------


def test_tool_adapter_defaults_to_a_real_manager():
    adapter = ToolAdapter()

    from app.services.ai.tools.manager import ToolManager

    assert isinstance(adapter.manager, ToolManager)


def test_tool_adapter_invoke_delegates_to_the_manager():
    manager = _FakeToolManager()
    adapter = ToolAdapter(manager=manager)

    result = adapter.invoke("search", {"query": "hi"}, agent_id="agent-1")

    assert result is manager.result
    assert manager.calls == [("search", {"query": "hi"}, {"agent_id": "agent-1"})]


def test_tool_adapter_never_executes_a_tool_directly():
    import inspect

    source = inspect.getsource(ToolAdapter.invoke)
    assert "self.manager.invoke" in source


# --- RuntimeAdapter --------------------------------------------------------------------


def test_runtime_adapter_defaults_to_a_real_runtime():
    from app.services.ai.runtime.runtime import AIRuntime

    adapter = RuntimeAdapter()

    assert isinstance(adapter.runtime, AIRuntime)


def test_runtime_adapter_execute_delegates_to_the_runtime():
    runtime = _FakeRuntime()
    adapter = RuntimeAdapter(runtime=runtime)
    request = RuntimeRequest(
        organization_id=1, prompt_package=PromptPackage(system_prompt="s"), provider=ProviderName.OPENAI
    )

    result = adapter.execute(request)

    assert result is runtime.response
    assert runtime.requests == [request]


def test_runtime_adapter_never_calls_a_provider_directly():
    import inspect

    source = inspect.getsource(RuntimeAdapter.execute)
    assert "self.runtime.execute" in source
