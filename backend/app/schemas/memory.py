from pydantic import BaseModel, ConfigDict


class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "general"
    title: str | None = None
    user_id: int | None = None


class MemoryUpdate(BaseModel):
    content: str | None = None
    memory_type: str | None = None
    title: str | None = None


class MemoryResponse(BaseModel):
    id: int
    organization_id: int
    user_id: int | None = None
    memory_type: str
    title: str | None = None
    content: str

    model_config = ConfigDict(from_attributes=True)


MemoryRead = MemoryResponse
