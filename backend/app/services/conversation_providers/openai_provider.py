"""OpenAIConversationProvider (P7.14): TetraCrest's first concrete,
production `ConversationProvider` - proving the provider architecture
built for this exact seam actually reaches a real model.

Deliberately lives OUTSIDE app/services/ai/ entirely, in its own
top-level services package - mirroring app/services/embedding/'s own
precedent exactly (OpenAIEmbeddingProvider lives outside app/services/ai/
too), and matching app/services/ai's own architecture test's documented
intent verbatim: "a concrete provider implementation... is expected to
live in its own module, outside this package's reach" (see
app/tests/architecture/dependency_rules.py's VENDOR_MODULE_BLOCKLIST
comment). Every module actually under app/services/ai/ - including
ConversationProvider/ConversationProviderRegistry/
ConversationProviderFactory, all in app/services/ai/conversation/, which
this module imports and implements - stays free of any vendor SDK/HTTP
import, verified structurally by that same architecture test.

Talks to OpenAI's Chat Completions API directly over HTTP (no `openai`
SDK dependency), the same way OpenAIEmbeddingProvider
(app/services/embedding/openai_provider.py) talks to OpenAI's own
/v1/embeddings endpoint - a plain httpx call with errors translated into
this platform's own AIError taxonomy (app.services.ai.shared.exceptions),
never a provider-specific error type.

Retry ownership (P7.14 §11): deliberately NO internal retry loop here,
unlike OpenAIEmbeddingProvider's own internal exponential backoff.
Embedding calls have no wrapper of their own; conversation calls always
go through RuntimeExecutor (app.services.ai.runtime.execution), which
already owns retry via its own `max_retries` (defaulting to 0 - no retry
- until a caller explicitly configures otherwise). Retrying here too
would silently multiply attempts. This provider raises once per call;
RuntimeExecutor decides whether/how to retry.

Timeout (P7.14 §3 inspection finding): RuntimeTimeout
(app.services.ai.runtime.timeout) is retrospective only - it lets a call
run to completion and then reports an overrun, it cannot abort an
in-flight network call. This provider therefore enforces its own real,
request-level httpx timeout (`_REQUEST_TIMEOUT_SECONDS`, or
`config.timeout` when explicitly set) so a hung connection cannot block
forever - RuntimeTimeout remains a correct backstop on top of this, not
the only protection.

Known limitation, not fixed here (out of this milestone's scope):
RuntimeExecutor._build_config()/AIRuntime._build_config() construct
ConversationProviderConfig with only model/temperature/max_tokens - they
never populate config.api_key or config.timeout from the request. This
provider resolves its own api_key from Settings when config.api_key is
unset (exactly what P7.14 §7 requires - credentials come from
configuration, never hardcoded), and falls back to its own
_REQUEST_TIMEOUT_SECONDS when config.timeout is unset, for the same
reason.
"""

import httpx

from app.services.ai.conversation.base_provider import ConversationProvider
from app.services.ai.conversation.types import ConversationResponse
from app.services.ai.providers.enums import ProviderName
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
from app.services.ai.shared.response import AIResponseMetadata, FinishReason, ProviderResponse, UsageDetails
from app.services.prompt_builder.types import PromptPackage
from settings import get_settings

CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
_REQUEST_TIMEOUT_SECONDS = 30.0

# OpenAI's own finish_reason vocabulary, normalized onto FinishReason -
# see FinishReason's own docstring (app.services.ai.shared.response) for
# why this mapping exists at all: every vendor reports this differently.
_FINISH_REASON_MAP: dict[str, FinishReason] = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
    "tool_calls": FinishReason.TOOL_CALL,
    "function_call": FinishReason.TOOL_CALL,
}


class OpenAIConversationProvider(ConversationProvider):
    def __init__(self, config: ConversationProviderConfig | None = None) -> None:
        self.config = config or ConversationProviderConfig()
        settings = get_settings()
        self.api_key = self.config.api_key or settings.openai_api_key
        self.model = self.config.model or settings.conversation_model
        self.timeout = self.config.timeout or _REQUEST_TIMEOUT_SECONDS

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return self.model

    def health_check(self) -> bool:
        """Report whether an API key is configured - deliberately does
        not make a real request, mirroring
        OpenAIEmbeddingProvider.health_check()'s own precedent exactly:
        spending a billed call on a health check isn't appropriate, and
        OpenAI has no free "ping" endpoint."""
        return bool(self.api_key)

    def generate(self, prompt_package: PromptPackage) -> ConversationResponse:
        if not self.api_key:
            raise AuthenticationError("OpenAI API key is not configured")

        messages = self._build_messages(prompt_package)
        payload: dict[str, object] = {"model": self.model, "messages": messages}
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.max_tokens is not None:
            payload["max_tokens"] = self.config.max_tokens

        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.config.organization:
            headers["OpenAI-Organization"] = self.config.organization
        headers.update(self.config.headers)

        try:
            response = httpx.post(CHAT_COMPLETIONS_URL, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise self._translate_http_error(exc.response) from exc
        except httpx.TimeoutException as exc:
            raise AITimeoutError(f"OpenAI request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"OpenAI request failed: {exc}") from exc

        return self._parse_response(response)

    @staticmethod
    def _build_messages(prompt_package: PromptPackage) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if prompt_package.system_prompt:
            messages.append({"role": "system", "content": prompt_package.system_prompt})
        messages.extend({"role": message.role, "content": message.content} for message in prompt_package.messages)
        if not messages:
            raise InvalidRequestError("Cannot send an empty prompt to OpenAI - system_prompt and messages are both empty")
        return messages

    @staticmethod
    def _translate_http_error(response: httpx.Response) -> AIError:
        """Maps OpenAI's HTTP status + error body onto this platform's
        own AIError taxonomy (app.services.ai.shared.exceptions) - never
        a second, provider-specific error hierarchy (P7.14 §10)."""
        message = f"HTTP {response.status_code}"
        code = None
        try:
            body = response.json()
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict):
                message = error.get("message", message)
                code = error.get("code")
        except (ValueError, AttributeError):
            pass

        status = response.status_code
        if status in (401, 403):
            return AuthenticationError(f"OpenAI authentication failed: {message}")
        if status == 429:
            if code == "insufficient_quota":
                return QuotaExceededError(f"OpenAI quota exceeded: {message}")
            return RateLimitError(f"OpenAI rate limit exceeded: {message}")
        if status == 404:
            return ModelNotFoundError(f"OpenAI model not found: {message}")
        if status in (400, 422):
            if code == "content_policy_violation":
                return ContentFilterError(f"OpenAI content filter rejected the request: {message}")
            return InvalidRequestError(f"OpenAI rejected the request: {message}")
        if status >= 500:
            return ProviderUnavailableError(f"OpenAI server error ({status}): {message}")
        return AIError(f"OpenAI request failed ({status}): {message}")

    def _parse_response(self, response: httpx.Response) -> ConversationResponse:
        try:
            body = response.json()
            choice = body["choices"][0]
            text = choice["message"]["content"] or ""
            finish_reason = _FINISH_REASON_MAP.get(choice.get("finish_reason"), FinishReason.UNKNOWN)
            model = body.get("model") or self.model
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIError(f"OpenAI response was malformed: {exc}") from exc

        usage = None
        usage_body = body.get("usage")
        if isinstance(usage_body, dict):
            usage = UsageDetails(
                prompt_tokens=usage_body.get("prompt_tokens", 0),
                completion_tokens=usage_body.get("completion_tokens", 0),
                total_tokens=usage_body.get("total_tokens", 0),
            )

        metadata = AIResponseMetadata(provider=ProviderName.OPENAI, model=model, finish_reason=finish_reason)
        provider_response = ProviderResponse(metadata=metadata, usage=usage, raw_response=body)
        return ConversationResponse(text=text, response=provider_response)
