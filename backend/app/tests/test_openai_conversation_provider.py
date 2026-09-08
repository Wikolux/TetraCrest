"""OpenAIConversationProvider (P7.14): request mapping, response
normalization, error translation, and the registry/factory/runtime
integration - all deterministic, no network access, no real credentials.
Mirrors OpenAIEmbeddingProvider's own httpx-mocking test convention
exactly (app/tests/test_embedding_service.py)."""

import httpx
import pytest

from app.services.ai.conversation.base_provider import ConversationProvider
from app.services.ai.conversation.provider_factory import ConversationProviderFactory
from app.services.ai.conversation.registry import ConversationProviderRegistry
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeRequest
from app.services.ai.shared.exceptions import (
    AIError,
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    ModelNotFoundError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
)
from app.services.ai.shared.exceptions import TimeoutError as AITimeoutError
from app.services.ai.shared.provider_config import ConversationProviderConfig
from app.services.conversation_providers.openai_provider import CHAT_COMPLETIONS_URL, OpenAIConversationProvider
from app.services.prompt_builder.types import PromptMessage, PromptPackage

ORG_ID = 1


def _fake_post(json_body: dict, status_code: int = 200):
    def _post(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(status_code, json=json_body, request=request)

    return _post


def _fake_post_connection_error():
    def _post(url, **kwargs):
        raise httpx.ConnectError("Connection failed", request=httpx.Request("POST", url))

    return _post


def _fake_post_timeout():
    def _post(url, **kwargs):
        raise httpx.ReadTimeout("Read timed out", request=httpx.Request("POST", url))

    return _post


def _chat_response(text="Hello!", finish_reason="stop", model="gpt-4o-mini", usage=None):
    return {
        "id": "chatcmpl-test",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": finish_reason}],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _package(system="You are helpful.", messages=(("user", "Hi"),)):
    return PromptPackage(system_prompt=system, messages=[PromptMessage(role=r, content=c) for r, c in messages])


# --- request mapping ---------------------------------------------------------------------------


def test_generate_sends_system_prompt_and_messages_in_order(monkeypatch):
    captured = {}

    def _post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        request = httpx.Request("POST", url)
        return httpx.Response(200, json=_chat_response(), request=request)

    monkeypatch.setattr(httpx, "post", _post)
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key", model="gpt-4o-mini"))

    provider.generate(_package(system="Be terse.", messages=(("user", "Hi"), ("assistant", "Hello"), ("user", "How are you?"))))

    assert captured["url"] == CHAT_COMPLETIONS_URL
    assert captured["json"]["model"] == "gpt-4o-mini"
    assert captured["json"]["messages"] == [
        {"role": "system", "content": "Be terse."},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "How are you?"},
    ]
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_generate_omits_system_message_when_system_prompt_is_empty(monkeypatch):
    captured = {}

    def _post(url, **kwargs):
        captured["json"] = kwargs["json"]
        request = httpx.Request("POST", url)
        return httpx.Response(200, json=_chat_response(), request=request)

    monkeypatch.setattr(httpx, "post", _post)
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    provider.generate(PromptPackage(system_prompt="", messages=[PromptMessage(role="user", content="Hi")]))

    assert captured["json"]["messages"] == [{"role": "user", "content": "Hi"}]


def test_generate_maps_temperature_and_max_tokens_when_set(monkeypatch):
    captured = {}

    def _post(url, **kwargs):
        captured["json"] = kwargs["json"]
        request = httpx.Request("POST", url)
        return httpx.Response(200, json=_chat_response(), request=request)

    monkeypatch.setattr(httpx, "post", _post)
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key", temperature=0.2, max_tokens=100))

    provider.generate(_package())

    assert captured["json"]["temperature"] == 0.2
    assert captured["json"]["max_tokens"] == 100


def test_generate_omits_temperature_and_max_tokens_when_unset(monkeypatch):
    captured = {}

    def _post(url, **kwargs):
        captured["json"] = kwargs["json"]
        request = httpx.Request("POST", url)
        return httpx.Response(200, json=_chat_response(), request=request)

    monkeypatch.setattr(httpx, "post", _post)
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    provider.generate(_package())

    assert "temperature" not in captured["json"]
    assert "max_tokens" not in captured["json"]


def test_generate_rejects_a_completely_empty_prompt():
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    with pytest.raises(InvalidRequestError, match="empty prompt"):
        provider.generate(PromptPackage(system_prompt="", messages=[]))


# --- credentials/model resolution ---------------------------------------------------------------


def test_generate_requires_an_api_key(monkeypatch):
    from settings import get_settings

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        provider = OpenAIConversationProvider(ConversationProviderConfig(api_key=None))
        with pytest.raises(AuthenticationError, match="API key is not configured"):
            provider.generate(_package())
    finally:
        get_settings.cache_clear()


def test_health_check_reports_configured_state_without_a_real_request(monkeypatch):
    from settings import get_settings

    def _post(*args, **kwargs):
        raise AssertionError("health_check() must never make a real HTTP request")

    monkeypatch.setattr(httpx, "post", _post)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        assert OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key")).health_check() is True
        assert OpenAIConversationProvider(ConversationProviderConfig(api_key=None)).health_check() is False
    finally:
        get_settings.cache_clear()


def test_provider_falls_back_to_settings_when_config_omits_api_key_and_model(monkeypatch):
    from settings import get_settings

    monkeypatch.setenv("OPENAI_API_KEY", "from-settings")
    monkeypatch.setenv("CONVERSATION_MODEL", "gpt-test-default")
    get_settings.cache_clear()
    try:
        provider = OpenAIConversationProvider(ConversationProviderConfig())

        assert provider.api_key == "from-settings"
        assert provider.model_name == "gpt-test-default"
    finally:
        get_settings.cache_clear()


def test_provider_name_and_model_name():
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="k", model="gpt-4o-mini"))
    assert provider.provider_name == ProviderName.OPENAI
    assert provider.model_name == "gpt-4o-mini"


# --- response normalization ----------------------------------------------------------------------


def test_generate_normalizes_a_successful_response(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post(_chat_response(text="Hi there!", finish_reason="stop")))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    result = provider.generate(_package())

    assert result.text == "Hi there!"
    assert result.provider == ProviderName.OPENAI
    assert result.model == "gpt-4o-mini"
    assert result.finish_reason.value == "stop"
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
    assert result.usage.total_tokens == 15
    assert result.raw_response is not None


@pytest.mark.parametrize(
    "openai_finish_reason,expected",
    [("stop", "stop"), ("length", "length"), ("content_filter", "content_filter"), ("tool_calls", "tool_call"), ("something_new", "unknown")],
)
def test_generate_maps_every_known_finish_reason(monkeypatch, openai_finish_reason, expected):
    monkeypatch.setattr(httpx, "post", _fake_post(_chat_response(finish_reason=openai_finish_reason)))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    result = provider.generate(_package())

    assert result.finish_reason.value == expected


def test_generate_handles_a_response_with_no_usage_block(monkeypatch):
    body = _chat_response()
    del body["usage"]
    monkeypatch.setattr(httpx, "post", _fake_post(body))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    result = provider.generate(_package())

    assert result.usage is None


# --- error normalization --------------------------------------------------------------------------


def test_generate_wraps_401_as_authentication_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "Invalid API key", "code": "invalid_api_key"}}, status_code=401))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="bad-key"))

    with pytest.raises(AuthenticationError, match="Invalid API key"):
        provider.generate(_package())


def test_generate_wraps_429_as_rate_limit_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "Too many requests", "code": "rate_limit_exceeded"}}, status_code=429))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    with pytest.raises(RateLimitError, match="Too many requests"):
        provider.generate(_package())


def test_generate_wraps_429_with_insufficient_quota_as_quota_exceeded_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "You exceeded your quota", "code": "insufficient_quota"}}, status_code=429))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    with pytest.raises(QuotaExceededError, match="exceeded your quota"):
        provider.generate(_package())


def test_generate_wraps_404_as_model_not_found_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "model not found", "code": "model_not_found"}}, status_code=404))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    with pytest.raises(ModelNotFoundError):
        provider.generate(_package())


def test_generate_wraps_400_as_invalid_request_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "bad request"}}, status_code=400))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    with pytest.raises(InvalidRequestError):
        provider.generate(_package())


def test_generate_wraps_content_policy_violation_as_content_filter_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "flagged", "code": "content_policy_violation"}}, status_code=400))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    with pytest.raises(ContentFilterError):
        provider.generate(_package())


def test_generate_wraps_5xx_as_provider_unavailable_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "server error"}}, status_code=503))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    with pytest.raises(ProviderUnavailableError):
        provider.generate(_package())


def test_generate_wraps_connection_error_as_provider_unavailable_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post_connection_error())
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    with pytest.raises(ProviderUnavailableError, match="OpenAI request failed"):
        provider.generate(_package())


def test_generate_wraps_timeout_as_platform_timeout_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post_timeout())
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    with pytest.raises(AITimeoutError, match="timed out"):
        provider.generate(_package())


def test_generate_wraps_malformed_response_body(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"unexpected": "shape"}))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="test-key"))

    with pytest.raises(AIError, match="malformed"):
        provider.generate(_package())


def test_generate_never_leaks_the_api_key_in_an_error_message(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "Invalid API key"}}, status_code=401))
    provider = OpenAIConversationProvider(ConversationProviderConfig(api_key="sk-super-secret-value"))

    with pytest.raises(AuthenticationError) as exc_info:
        provider.generate(_package())

    assert "sk-super-secret-value" not in str(exc_info.value)


# --- registry/factory/runtime integration ---------------------------------------------------------


def test_openai_is_registered_in_the_conversation_provider_registry():
    assert ConversationProviderRegistry.is_registered(ProviderName.OPENAI)
    assert ConversationProviderRegistry.get(ProviderName.OPENAI) is OpenAIConversationProvider


def test_factory_constructs_a_real_openai_provider():
    provider = ConversationProviderFactory.create(ProviderName.OPENAI, ConversationProviderConfig(api_key="test-key"))

    assert isinstance(provider, OpenAIConversationProvider)
    assert isinstance(provider, ConversationProvider)


def test_runtime_end_to_end_through_the_real_openai_provider(monkeypatch):
    """The exact chain P7.14 exists to prove: RuntimeAdapter -> AIRuntime
    -> RuntimeExecutor -> ConversationProviderFactory ->
    ConversationProviderRegistry -> OpenAIConversationProvider -> a
    normalized RuntimeResponse - with the network mocked, never real."""
    from settings import get_settings

    monkeypatch.setattr(httpx, "post", _fake_post(_chat_response(text="Real provider, mocked transport.")))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        runtime = AIRuntime()
        request = RuntimeRequest(organization_id=ORG_ID, prompt_package=_package(), provider=ProviderName.OPENAI)

        response = runtime.execute(request)

        assert response.success is True
        assert response.provider == ProviderName.OPENAI
        assert response.conversation_response.text == "Real provider, mocked transport."
        assert response.usage.total_tokens == 15
    finally:
        get_settings.cache_clear()


def test_runtime_reports_failure_not_an_exception_when_openai_call_fails(monkeypatch):
    from settings import get_settings

    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "Invalid API key"}}, status_code=401))
    monkeypatch.setenv("OPENAI_API_KEY", "a-key-openai-will-reject")
    get_settings.cache_clear()
    try:
        runtime = AIRuntime()
        request = RuntimeRequest(organization_id=ORG_ID, prompt_package=_package(), provider=ProviderName.OPENAI, model="gpt-4o-mini")

        response = runtime.execute(request)

        assert response.success is False
        assert response.error is not None
    finally:
        get_settings.cache_clear()


# --- architecture protections (P7.14 §22) -----------------------------------------------------


def test_no_hardcoded_api_key_literal_in_the_provider_source():
    import inspect
    import re

    import app.services.conversation_providers.openai_provider as provider_module

    source = inspect.getsource(provider_module)
    assert not re.search(r"sk-[A-Za-z0-9]{16,}", source), "a real-looking OpenAI API key literal was found in provider source"


def test_exactly_one_air_runtime_class_exists():
    """P7.14 §22: no second runtime introduced by this milestone."""
    import ast

    from app.tests.architecture.dependency_rules import AI_ROOT_DIR

    matches = []
    for path in AI_ROOT_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "AIRuntime":
                matches.append(str(path))
    assert len(matches) == 1, f"Expected exactly one AIRuntime class, found: {matches}"


def test_personal_os_never_imports_the_concrete_openai_provider():
    import ast
    from pathlib import Path

    personal_os_dir = Path(__file__).resolve().parents[2] / "app" / "services" / "personal_os"
    violations = []
    for path in personal_os_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.services.conversation_providers"):
                violations.append(str(path))
    assert violations == [], f"Personal OS must never import a concrete provider directly: {violations}"


def test_specialists_never_import_the_concrete_openai_provider():
    import ast
    from pathlib import Path

    specialists_dir = Path(__file__).resolve().parents[2] / "app" / "services" / "ai" / "agents" / "specialists"
    violations = []
    for path in specialists_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.services.conversation_providers"):
                violations.append(str(path))
    assert violations == [], f"Specialists must never import a concrete provider directly: {violations}"


def test_no_other_module_calls_the_openai_chat_completions_endpoint_directly():
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1]
    provider_file = app_dir / "services" / "conversation_providers" / "openai_provider.py"
    violations = []
    for path in app_dir.rglob("*.py"):
        if path == provider_file or "/tests/" in str(path):
            continue
        text = path.read_text()
        if "api.openai.com/v1/chat/completions" in text:
            violations.append(str(path))
    assert violations == [], f"Only openai_provider.py may reference the chat completions endpoint directly: {violations}"


# --- P7.14 §16: an existing, UNMODIFIED Personal OS narration path consumes a real ---------------
# --- (mocked-transport) provider response, never its deterministic fallback ---------------------


def test_adaptation_flow_present_consumes_a_real_provider_response_not_the_fallback(monkeypatch):
    """AdaptationFlow.present() (app/services/personal_os/adaptation_flow.py,
    unmodified by P7.14) already builds a real RuntimeRequest and calls
    RuntimeAdapter().execute() when no fake runtime is injected - every
    P7.10-P7.12 test used a _FakeRuntime specifically to exercise the
    honest deterministic fallback. This test does the opposite: default,
    real RuntimeAdapter/AIRuntime, mocked HTTP transport standing in for
    the network only - proving the P7.14 provider bridge reaches all the
    way into already-built Personal OS code with zero changes to it."""
    from datetime import date

    from settings import get_settings

    from app.services.personal_os.adaptation import AdaptationTarget
    from app.services.personal_os.adaptation_flow import AdaptationFlow
    from app.services.personal_os.adaptation_repository import InMemoryAdaptationRepository
    from app.services.personal_os.pattern import Pattern, PatternEvidenceItem
    from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, InferredPattern, ObservedFact
    from app.services.personal_os.shared.types import AdaptationScope, Confidence, PatternStatus, PatternType

    expected_text = "Genuinely generated by a real (mocked-transport) OpenAI call, not the deterministic fallback."
    monkeypatch.setattr(httpx, "post", _fake_post(_chat_response(text=expected_text)))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:

        facts = (ObservedFact(statement="fact one"), ObservedFact(statement="fact two"))
        inferred = InferredPattern(statement="a recurring pattern", supporting_facts=facts)
        hypothesis = Hypothesis(statement="estimates may be optimistic", explains=inferred)
        recommendation = GrowthRecommendation(statement="Add a 50% buffer.", responds_to=hypothesis)
        pattern = Pattern(
            pattern_id="p1",
            pattern_type=PatternType.REPEATED_POSTPONEMENT,
            observation_window_start=date(2026, 7, 1),
            observation_window_end=date(2026, 7, 14),
            evidence=(PatternEvidenceItem(observation_date=date(2026, 7, 1), activity_description="x", activity_category="learning", status="postponed"),),
            observed_facts=facts,
            pattern_statement="4 activities postponed",
            confidence=Confidence.MEDIUM,
            possible_hypotheses=(hypothesis,),
            recommendation=recommendation,
            status=PatternStatus.CONFIRMED,
        )

        repo = InMemoryAdaptationRepository()
        flow = AdaptationFlow(repo)  # no fake runtime injected - the real RuntimeAdapter/AIRuntime default
        target = AdaptationTarget(scope=AdaptationScope.USER_PREFERENCE, target_id="1")
        proposed = flow.propose(pattern, organization_id=1, user_id=1, target=target)

        narrative = flow.present(proposed, pattern, organization_id=1)

        assert narrative == expected_text
        assert "Proposed change:" not in narrative  # AdaptationFlow.present()'s own fallback phrasing
    finally:
        get_settings.cache_clear()
