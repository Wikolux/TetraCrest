from typing import Generic, TypeVar

from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, id: int) -> ModelType | None:
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_by_id_for_organization(
        self, id: int, organization_id: int, tenant_field: str = "organization_id"
    ) -> ModelType | None:
        """Fetch a row by id, but only if it belongs to the given tenant.

        Cross-tenant access and a missing row are intentionally indistinguishable
        (both return None) so callers never leak whether a resource exists in
        another organization.
        """
        obj = self.get_by_id(id)
        if not obj or getattr(obj, tenant_field) != organization_id:
            return None
        return obj

    def get_many_for_organization(
        self, ids: list[int], organization_id: int, tenant_field: str = "organization_id"
    ) -> list[ModelType]:
        """Fetch multiple rows by id in a single query, scoped to a tenant.

        Batches what would otherwise be N get_by_id_for_organization() calls
        (e.g. hydrating many vector-search matches at once) into one query.
        Ids that don't exist or belong to another organization are simply
        absent from the result, never raised - the same "don't reveal what
        exists elsewhere" rule get_by_id_for_organization already follows.
        """
        if not ids:
            return []
        return (
            self.db.query(self.model)
            .filter(self.model.id.in_(ids), getattr(self.model, tenant_field) == organization_id)
            .all()
        )

    def get_all(self, skip: int = 0, limit: int = 20):
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, obj_in) -> ModelType:
        self.db.add(obj_in)
        self.db.commit()
        self.db.refresh(obj_in)
        return obj_in

    def update(self, obj: ModelType, **fields) -> ModelType:
        for key, value in fields.items():
            setattr(obj, key, value)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelType) -> None:
        self.db.delete(obj)
        self.db.commit()
