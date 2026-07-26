from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization_id
from app.schemas.conversation import ConversationCreate, ConversationRead
from app.services.conversation_service import ConversationService
from database import get_db

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    return service.create_conversation(organization_id, user_id=payload.user_id, title=payload.title)


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    return service.list_conversations(organization_id, skip=skip, limit=limit)


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: int,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    conversation = service.get_conversation(conversation_id, organization_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.patch("/{conversation_id}/archive", response_model=ConversationRead)
def archive_conversation(
    conversation_id: int,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    conversation = service.archive_conversation(conversation_id, organization_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    if not service.delete_conversation(conversation_id, organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
