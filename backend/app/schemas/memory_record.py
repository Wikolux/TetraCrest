from pydantic import BaseModel, ConfigDict


class MemoryRecordCreate(BaseModel):
    memory_type: str = "general"
    key: str
    value: str
    organization_id: int


class MemoryRecordUpdate(BaseModel):
    memory_type: str | None = None
    key: str | None = None
    value: str | None = None


class MemoryRecordResponse(BaseModel):
    id: int
    memory_type: str
    key: str
    value: str
    organization_id: int

    model_config = ConfigDict(from_attributes=True)


MemoryRecordRead = MemoryRecordResponse
