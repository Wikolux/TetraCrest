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

    def list_for_organization(self, organization_id: int):
        return self.repo.get_by_organization(organization_id)
