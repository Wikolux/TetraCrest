from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.schemas.task import TaskCreate, TaskRead
from app.services.task_service import TaskService
from database import get_db

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    service = TaskService(db)
    return service.create(payload.title, payload.organization_id, payload.project_id, payload.assignee_id, payload.description)


@router.get("/project/{project_id}", response_model=list[TaskRead])
def list_tasks(project_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    return service.list_for_project(project_id)
