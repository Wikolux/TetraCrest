from enum import StrEnum


class ProviderName(StrEnum):
    """Every AI vendor this platform is designed to eventually support.

    A provider's identity is independent of which capability is being
    used - the same OPENAI value is used whether a future
    OpenAIConversationProvider, OpenAIVisionProvider, or
    OpenAIEmbeddingProvider (capability-specific classes, none of which
    exist yet) is being registered. UNKNOWN exists for callers that need
    to represent "no provider" without using None or an empty string.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    MISTRAL = "mistral"
    GROK = "grok"
    UNKNOWN = "unknown"
