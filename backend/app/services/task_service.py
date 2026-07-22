from sqlalchemy.orm import Session

from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from database import SessionLocal


class TaskService:
    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()
        self.repo = TaskRepository(self.db)

    def create(self, title: str, organization_id: int, project_id: int, assignee_id: int | None = None, description: str | None = None) -> Task:
        task = Task(title=title, organization_id=organization_id, project_id=project_id, assignee_id=assignee_id, description=description, status="pending")
        return self.repo.create(task)

    def list_for_project(self, project_id: int):
        return self.repo.get_by_project(project_id)
