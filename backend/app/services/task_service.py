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

    def list_for_project(self, project_id: int, skip: int = 0, limit: int = 20):
        return self.repo.get_by_project(project_id, skip=skip, limit=limit)

    def update(self, task_id: int, organization_id: int, **fields) -> Task | None:
        task = self.repo.get_by_id_for_organization(task_id, organization_id)
        if not task:
            return None
        return self.repo.update(task, **fields)

    def delete(self, task_id: int, organization_id: int) -> bool:
        task = self.repo.get_by_id_for_organization(task_id, organization_id)
        if not task:
            return False
        self.repo.delete(task)
        return True
