from pydantic import BaseModel, ConfigDict


class KnowledgeDocumentCreate(BaseModel):
    title: str
    content: str
    document_type: str = "general"
    source: str | None = None
    organization_id: int
    created_by: int | None = None


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    document_type: str | None = None
    source: str | None = None
    created_by: int | None = None


class KnowledgeDocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    document_type: str
    source: str | None = None
    organization_id: int
    created_by: int | None = None

    model_config = ConfigDict(from_attributes=True)


KnowledgeDocumentRead = KnowledgeDocumentResponse
