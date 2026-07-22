from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    status: str = "planning"
    organization_id: int
    owner_id: int | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    status: str
    owner_id: int | None = None
    organization_id: int

    model_config = ConfigDict(from_attributes=True)


ProjectRead = ProjectResponse
