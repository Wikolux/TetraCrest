from pydantic import BaseModel, ConfigDict


class KnowledgeDocumentCreate(BaseModel):
    title: str
    content: str
    document_type: str = "general"
    source: str | None = None
    organization_id: int
    created_by: int | None = None

    source_type: str = "manual"
    classification: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    storage_path: str | None = None
    source_url: str | None = None
    ingestion_status: str = "pending"
    metadata_json: str | None = None


class KnowledgeURLIngestRequest(BaseModel):
    url: str
    organization_id: int
    created_by: int | None = None
    title: str | None = None


class KnowledgeYouTubeIngestRequest(BaseModel):
    url: str
    organization_id: int
    created_by: int | None = None
    title: str | None = None


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    document_type: str | None = None
    source: str | None = None
    created_by: int | None = None

    source_type: str | None = None
    classification: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    storage_path: str | None = None
    source_url: str | None = None
    ingestion_status: str | None = None
    metadata_json: str | None = None


class KnowledgeDocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    document_type: str
    source: str | None = None
    organization_id: int
    created_by: int | None = None

    source_type: str
    classification: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    storage_path: str | None = None
    source_url: str | None = None
    ingestion_status: str
    metadata_json: str | None = None

    model_config = ConfigDict(from_attributes=True)


KnowledgeDocumentRead = KnowledgeDocumentResponse
