from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    title: str | None = None
    user_id: int | None = None


class ConversationResponse(BaseModel):
    id: int
    organization_id: int
    user_id: int | None = None
    title: str | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)


ConversationRead = ConversationResponse
