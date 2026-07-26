from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization_id
from app.schemas.memory import MemoryCreate, MemoryRead, MemoryUpdate
from app.services.ai_memory_service import AIMemoryService
from database import get_db

router = APIRouter(prefix="/memories", tags=["memories"])


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = AIMemoryService(db)
    return service.create_memory(
        organization_id=organization_id,
        content=payload.content,
        user_id=payload.user_id,
        memory_type=payload.memory_type,
        title=payload.title,
    )


@router.get("", response_model=list[MemoryRead])
def list_memories(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = AIMemoryService(db)
    return service.list_memories(organization_id, skip=skip, limit=limit)


@router.get("/{memory_id}", response_model=MemoryRead)
def get_memory(
    memory_id: int,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = AIMemoryService(db)
    memory = service.get_memory(memory_id, organization_id)
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return memory


@router.put("/{memory_id}", response_model=MemoryRead)
def update_memory(
    memory_id: int,
    payload: MemoryUpdate,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = AIMemoryService(db)
    memory = service.update_memory(memory_id, organization_id, **payload.model_dump(exclude_unset=True))
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return memory


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: int,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = AIMemoryService(db)
    if not service.delete_memory(memory_id, organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
