from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization_id
from app.schemas.knowledge_document import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentRead,
    KnowledgeDocumentUpdate,
    KnowledgeURLIngestRequest,
    KnowledgeYouTubeIngestRequest,
)
from app.services.knowledge_service import KnowledgeService
from database import get_db

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("", response_model=KnowledgeDocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(payload: KnowledgeDocumentCreate, db: Session = Depends(get_db)):
    service = KnowledgeService(db)
    return service.create(payload.title, payload.content, payload.organization_id, payload.created_by)


@router.post("/ingest", response_model=KnowledgeDocumentRead, status_code=status.HTTP_201_CREATED)
def ingest_document(
    organization_id: int = Form(...),
    title: str | None = Form(None),
    content: str | None = Form(None),
    created_by: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    service = KnowledgeService(db)
    return service.ingest_upload(
        file, organization_id, created_by=created_by, title=title, content=content
    )


@router.post("/ingest/url", response_model=KnowledgeDocumentRead, status_code=status.HTTP_201_CREATED)
def ingest_url_document(payload: KnowledgeURLIngestRequest, db: Session = Depends(get_db)):
    service = KnowledgeService(db)
    return service.ingest_url(
        payload.url, payload.organization_id, created_by=payload.created_by, title=payload.title
    )


@router.post("/ingest/youtube", response_model=KnowledgeDocumentRead, status_code=status.HTTP_201_CREATED)
def ingest_youtube_document(payload: KnowledgeYouTubeIngestRequest, db: Session = Depends(get_db)):
    service = KnowledgeService(db)
    return service.ingest_youtube(
        payload.url, payload.organization_id, created_by=payload.created_by, title=payload.title
    )


@router.get("/organization/{organization_id}", response_model=list[KnowledgeDocumentRead])
def list_documents(
    organization_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = KnowledgeService(db)
    return service.list_for_organization(organization_id, skip=skip, limit=limit)


@router.patch("/{document_id}", response_model=KnowledgeDocumentRead)
def update_document(
    document_id: int,
    payload: KnowledgeDocumentUpdate,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = KnowledgeService(db)
    document = service.update(document_id, organization_id, **payload.model_dump(exclude_unset=True))
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = KnowledgeService(db)
    if not service.delete(document_id, organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")
