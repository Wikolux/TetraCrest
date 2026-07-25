from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization_id
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.task_service import TaskService
from database import get_db

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    service = TaskService(db)
    return service.create(payload.title, payload.organization_id, payload.project_id, payload.assignee_id, payload.description)


@router.get("/project/{project_id}", response_model=list[TaskRead])
def list_tasks(
    project_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = TaskService(db)
    return service.list_for_project(project_id, skip=skip, limit=limit)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = TaskService(db)
    task = service.update(task_id, organization_id, **payload.model_dump(exclude_unset=True))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = TaskService(db)
    if not service.delete(task_id, organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
