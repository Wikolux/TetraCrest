from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization_id
from app.schemas.conversation_message import ConversationMessageCreate, ConversationMessageRead
from app.services.conversation_message_service import ConversationMessageService
from database import get_db

router = APIRouter(prefix="/conversations", tags=["conversation-messages"])


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def add_message(
    conversation_id: int,
    payload: ConversationMessageCreate,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = ConversationMessageService(db)
    message = service.add_message(
        conversation_id, organization_id, content=payload.content, role=payload.role
    )
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return message


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessageRead])
def list_messages(
    conversation_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = ConversationMessageService(db)
    return service.list_messages(conversation_id, organization_id, skip=skip, limit=limit)


@router.get("/{conversation_id}/messages/{message_id}", response_model=ConversationMessageRead)
def get_message(
    conversation_id: int,
    message_id: int,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = ConversationMessageService(db)
    message = service.get_message(message_id, conversation_id, organization_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return message
