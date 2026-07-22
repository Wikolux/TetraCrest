from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    status: str = "pending"
    priority: str = "medium"
    project_id: int | None = None
    assignee_id: int | None = None
    organization_id: int


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    status: str
    priority: str
    project_id: int | None = None
    assignee_id: int | None = None
    organization_id: int

    model_config = ConfigDict(from_attributes=True)


TaskRead = TaskResponse
