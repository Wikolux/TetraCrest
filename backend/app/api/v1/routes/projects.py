from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.schemas.project import ProjectCreate, ProjectRead
from app.services.project_service import ProjectService
from database import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    service = ProjectService(db)
    return service.create(payload.name, payload.organization_id, payload.owner_id, payload.description)


@router.get("/organization/{organization_id}", response_model=list[ProjectRead])
def list_projects(organization_id: int, db: Session = Depends(get_db)):
    service = ProjectService(db)
    return service.list_for_organization(organization_id)
