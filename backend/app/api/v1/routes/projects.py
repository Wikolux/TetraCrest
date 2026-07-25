from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization_id
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import ProjectService
from database import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    service = ProjectService(db)
    return service.create(payload.name, payload.organization_id, payload.owner_id, payload.description)


@router.get("/organization/{organization_id}", response_model=list[ProjectRead])
def list_projects(
    organization_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = ProjectService(db)
    return service.list_for_organization(organization_id, skip=skip, limit=limit)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = ProjectService(db)
    project = service.update(project_id, organization_id, **payload.model_dump(exclude_unset=True))
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = ProjectService(db)
    if not service.delete(project_id, organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
