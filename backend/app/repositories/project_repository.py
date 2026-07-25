from app.models.project import Project
from app.repositories.base import BaseRepository
from sqlalchemy.orm import Session


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: Session):
        super().__init__(Project, db)

    def get_by_organization(self, organization_id: int, skip: int = 0, limit: int = 20):
        return (
            self.db.query(Project)
            .filter(Project.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
