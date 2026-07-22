from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.schemas.knowledge_document import KnowledgeDocumentCreate, KnowledgeDocumentRead
from app.services.knowledge_service import KnowledgeService
from database import get_db

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("", response_model=KnowledgeDocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(payload: KnowledgeDocumentCreate, db: Session = Depends(get_db)):
    service = KnowledgeService(db)
    return service.create(payload.title, payload.content, payload.organization_id, payload.created_by)


@router.get("/organization/{organization_id}", response_model=list[KnowledgeDocumentRead])
def list_documents(organization_id: int, db: Session = Depends(get_db)):
    service = KnowledgeService(db)
    return service.list_for_organization(organization_id)
