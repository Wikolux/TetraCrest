"""WikipediaSearchTool (P7.15): TetraCrest's first real, external,
read-only tool - proving the Tool Framework can execute a genuine,
side-effect-free network action under real, non-fail-open authorization.

Lives outside app/services/ai/ entirely, for the exact reason
OpenAIConversationProvider (P7.14) does: the platform's own
find_vendor_import_violations() architecture test forbids httpx/vendor
imports anywhere under app/services/ai/, with no carve-out for tools/ -
confirmed by inspection during P7.15's own Phase 0, not rediscovered by
a failing test this time.

Domain-locked, never a generic fetcher (P7.15 §9-§10): WIKIPEDIA_SEARCH_URL
is a fixed module-level constant. The caller-supplied `query` only ever
becomes the value of the `srsearch` URL query parameter, via httpx's own
`params=` encoding - it can never become the scheme, host, port, or path.
No string a caller supplies as `query` can redirect this tool to another
domain; this is proven directly by a dedicated test, not merely asserted
in this docstring.
"""

import re

import httpx

from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.schema import SchemaField, ToolSchema
from app.services.ai.tools.shared.types import Metadata

WIKIPEDIA_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
_REQUEST_TIMEOUT_SECONDS = 10.0
_MAX_RESULTS = 3
_NO_RESULTS_SUMMARY = "No Wikipedia results found."


def _strip_markup(text: str) -> str:
    """Wikipedia's own search snippets embed <span class="searchmatch">
    tags around matched terms - stripped so ToolResult.output is plain,
    readable text, never raw markup."""
    return re.sub(r"<[^>]+>", "", text)


class WikipediaSearchTool(BaseTool):
    @property
    def tool_id(self) -> str:
        return "wikipedia_search"

    @property
    def name(self) -> str:
        return "Wikipedia Search"

    @property
    def description(self) -> str:
        return "Looks up a query against Wikipedia's public search API and returns a short summary of the top results."

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset({ToolCapability.READ, ToolCapability.NETWORK, ToolCapability.SEARCH})

    @property
    def permissions(self) -> frozenset[ToolPermission]:
        return frozenset({ToolPermission.NETWORK})

    def input_schema(self) -> ToolSchema:
        return ToolSchema(fields=(SchemaField(name="query", type="string", required=True, description="The search query."),))

    def output_schema(self) -> ToolSchema:
        return ToolSchema(
            fields=(
                SchemaField(name="query", type="string"),
                SchemaField(name="result_count", type="integer"),
                SchemaField(name="results", type="array"),
            )
        )

    def validate(self, parameters: Metadata) -> None:
        query = parameters.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("WikipediaSearchTool requires a non-empty 'query' string")

    def health_check(self) -> bool:
        """No credentials to check, and a real reachability probe would
        spend a real request unnecessarily (mirrors
        OpenAIEmbeddingProvider.health_check()'s own "don't spend a real
        call on a health check" precedent, adapted for a tool that has
        nothing to check locally at all)."""
        return True

    def execute(self, context: ToolContext) -> ToolResult:
        query = context.parameters.get("query", "")

        try:
            response = httpx.get(
                WIKIPEDIA_SEARCH_URL,
                params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": _MAX_RESULTS},
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            return ToolResult(success=False, error=f"Wikipedia request timed out: {exc}")
        except httpx.HTTPError as exc:
            return ToolResult(success=False, error=f"Wikipedia request failed: {exc}")

        try:
            body = response.json()
            search_results = body["query"]["search"]
        except (ValueError, KeyError, TypeError) as exc:
            return ToolResult(success=False, error=f"Wikipedia response was malformed: {exc}")

        results = tuple(
            {"title": item.get("title", ""), "snippet": _strip_markup(item.get("snippet", ""))} for item in search_results
        )
        # A successful lookup with zero results is a real, honest outcome -
        # never confused with a network/tool failure (P7.15 §11).
        summary = "; ".join(f"{r['title']}: {r['snippet']}" for r in results) if results else _NO_RESULTS_SUMMARY

        return ToolResult(
            success=True,
            output=summary,
            structured_output={"query": query, "result_count": len(results), "results": list(results)},
        )
