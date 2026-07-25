from app.models.task import Task
from app.repositories.base import BaseRepository
from sqlalchemy.orm import Session


class TaskRepository(BaseRepository[Task]):
    def __init__(self, db: Session):
        super().__init__(Task, db)

    def get_by_project(self, project_id: int, skip: int = 0, limit: int = 20):
        return (
            self.db.query(Task)
            .filter(Task.project_id == project_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
