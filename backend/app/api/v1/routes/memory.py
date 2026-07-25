from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization_id
from app.schemas.memory_record import MemoryRecordCreate, MemoryRecordRead, MemoryRecordUpdate
from app.services.memory_service import MemoryService
from database import get_db

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("", response_model=MemoryRecordRead, status_code=status.HTTP_201_CREATED)
def create_memory(payload: MemoryRecordCreate, db: Session = Depends(get_db)):
    service = MemoryService(db)
    return service.create(payload.key, payload.value, payload.organization_id, payload.memory_type)


@router.get("/organization/{organization_id}", response_model=list[MemoryRecordRead])
def list_memory(
    organization_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = MemoryService(db)
    return service.list_for_organization(organization_id, skip=skip, limit=limit)


@router.patch("/{record_id}", response_model=MemoryRecordRead)
def update_memory(
    record_id: int,
    payload: MemoryRecordUpdate,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = MemoryService(db)
    record = service.update(record_id, organization_id, **payload.model_dump(exclude_unset=True))
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory record not found")
    return record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    record_id: int,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = MemoryService(db)
    if not service.delete(record_id, organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory record not found")
