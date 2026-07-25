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

    def list_all(self, skip: int = 0, limit: int = 20):
        return self.repo.get_all(skip=skip, limit=limit)

    def update(self, organization_id: int, caller_organization_id: int, **fields) -> Organization | None:
        # An Organization *is* the tenant, so "belongs to the caller's tenant" means
        # the target id must match the caller's own organization id.
        organization = self.repo.get_by_id_for_organization(
            organization_id, caller_organization_id, tenant_field="id"
        )
        if not organization:
            return None
        return self.repo.update(organization, **fields)

    def delete(self, organization_id: int, caller_organization_id: int) -> bool:
        organization = self.repo.get_by_id_for_organization(
            organization_id, caller_organization_id, tenant_field="id"
        )
        if not organization:
            return False
        self.repo.delete(organization)
        return True
