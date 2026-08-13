from dataclasses import dataclass


@dataclass(frozen=True)
class TokenUsage:
    """Generic token accounting for a single provider call.

    Deliberately provider-agnostic: every provider reports usage in this
    shape regardless of what its own SDK/response calls these fields
    (e.g. OpenAI's prompt_tokens/completion_tokens vs. Anthropic's
    input_tokens/output_tokens both map onto this one shape).
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class ProviderCapabilities:
    """What a given provider/model combination can actually do.

    Populated by each concrete provider (none exist yet) so calling code
    can branch on capability - "does this support vision" - rather than
    on provider identity - "is this OpenAI". All fields default to the
    safest/most conservative value (unsupported / zero) so a provider
    that doesn't override a field is never assumed capable of something
    it never declared.

    supports_vision means understanding image input; supports_images
    means producing image output - deliberately distinct flags, since a
    provider can plausibly have either without the other. supports_tools
    and supports_function_calling are also kept distinct: several real
    provider APIs (OpenAI's history included) have shipped an older
    function-calling mechanism alongside a newer, broader tool-use one,
    and a provider may support one without the other.

    supports_json_mode already covers what "supports_json" would mean -
    not duplicated under a second name.
    """

    supports_streaming: bool = False
    supports_tools: bool = False
    supports_json_mode: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    max_context_tokens: int = 0
    supports_images: bool = False
    supports_audio: bool = False
    supports_embeddings: bool = False
    supports_function_calling: bool = False
    supports_long_context: bool = False
