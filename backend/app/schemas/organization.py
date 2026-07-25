from pydantic import BaseModel, ConfigDict


class OrganizationCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None


class OrganizationResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    active: bool

    model_config = ConfigDict(from_attributes=True)


OrganizationRead = OrganizationResponse
