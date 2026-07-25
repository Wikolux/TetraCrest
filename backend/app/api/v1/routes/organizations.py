from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization_id
from app.schemas.organization import OrganizationCreate, OrganizationRead, OrganizationUpdate
from app.services.organization_service import OrganizationService
from database import get_db

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationCreate, db: Session = Depends(get_db)):
    service = OrganizationService(db)
    return service.create(payload.name, payload.slug, payload.description)


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = OrganizationService(db)
    return service.list_all(skip=skip, limit=limit)


@router.get("/{organization_id}", response_model=OrganizationRead)
def get_organization(organization_id: int, db: Session = Depends(get_db)):
    service = OrganizationService(db)
    organization = service.get_by_id(organization_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.patch("/{organization_id}", response_model=OrganizationRead)
def update_organization(
    organization_id: int,
    payload: OrganizationUpdate,
    caller_organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = OrganizationService(db)
    organization = service.update(
        organization_id, caller_organization_id, **payload.model_dump(exclude_unset=True)
    )
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    organization_id: int,
    caller_organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    service = OrganizationService(db)
    if not service.delete(organization_id, caller_organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
