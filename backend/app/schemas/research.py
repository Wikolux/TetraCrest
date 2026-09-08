from pydantic import BaseModel


class ResearchLookupRequest(BaseModel):
    query: str


class ResearchLookupResponse(BaseModel):
    success: bool
    summary: str = ""
    findings: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    error: str | None = None
