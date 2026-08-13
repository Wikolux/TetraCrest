"""Pure rendering functions for a built PromptPackage.

Neither function mutates its argument or anything reachable from it - each
just reads package.messages/package.sections/package.system_prompt and
builds a brand new return value. Provider-agnostic: nothing here knows
about OpenAI, Anthropic, or Gemini message-format conventions - a real LLM
Service would adapt render_messages()'s plain {"role", "content"} dicts
into whatever shape a specific provider's SDK expects.
"""

from app.services.prompt_builder.types import PromptPackage


def render_messages(package: PromptPackage) -> list[dict[str, str]]:
    """Render package.messages as plain {"role", "content"} dicts, in order."""
    return [{"role": message.role, "content": message.content} for message in package.messages]


def render_text(package: PromptPackage) -> str:
    """Render the whole prompt as a single readable text block.

    Order: System Prompt, then each PromptSection in the order
    PromptBuilder already assembled them - Instructions, Retrieved
    Context, Conversation (if present), User Query. No markdown; each
    block is just "Title:\\ncontent", separated by a blank line.
    """
    blocks = [f"System Prompt:\n{package.system_prompt}"]
    blocks.extend(f"{section.title}:\n{section.content}" for section in package.sections)
    return "\n\n".join(blocks)
