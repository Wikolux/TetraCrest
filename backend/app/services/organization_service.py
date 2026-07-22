from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.repositories.organization_repository import OrganizationRepository
from database import SessionLocal


class OrganizationService:
    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()
        self.repo = OrganizationRepository(self.db)

    def create(self, name: str, slug: str, description: str | None = None) -> Organization:
        org = Organization(name=name, slug=slug, description=description, active=True)
        return self.repo.create(org)

    def get_by_id(self, organization_id: int) -> Organization | None:
        return self.repo.get_by_id(organization_id)
