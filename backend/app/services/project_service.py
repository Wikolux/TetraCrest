from sqlalchemy.orm import Session

from app.models.project import Project
from app.repositories.project_repository import ProjectRepository
from database import SessionLocal


class ProjectService:
    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()
        self.repo = ProjectRepository(self.db)

    def create(self, name: str, organization_id: int, owner_id: int | None = None, description: str | None = None) -> Project:
        project = Project(name=name, organization_id=organization_id, owner_id=owner_id, description=description)
        return self.repo.create(project)

    def list_for_organization(self, organization_id: int, skip: int = 0, limit: int = 20):
        return self.repo.get_by_organization(organization_id, skip=skip, limit=limit)

    def update(self, project_id: int, organization_id: int, **fields) -> Project | None:
        project = self.repo.get_by_id_for_organization(project_id, organization_id)
        if not project:
            return None
        return self.repo.update(project, **fields)

    def delete(self, project_id: int, organization_id: int) -> bool:
        project = self.repo.get_by_id_for_organization(project_id, organization_id)
        if not project:
            return False
        self.repo.delete(project)
        return True
