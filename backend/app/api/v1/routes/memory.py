from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.schemas.memory_record import MemoryRecordCreate, MemoryRecordRead
from app.services.memory_service import MemoryService
from database import get_db

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("", response_model=MemoryRecordRead, status_code=status.HTTP_201_CREATED)
def create_memory(payload: MemoryRecordCreate, db: Session = Depends(get_db)):
    service = MemoryService(db)
    return service.create(payload.key, payload.value, payload.organization_id, payload.memory_type)


@router.get("/organization/{organization_id}", response_model=list[MemoryRecordRead])
def list_memory(organization_id: int, db: Session = Depends(get_db)):
    service = MemoryService(db)
    return service.list_for_organization(organization_id)
