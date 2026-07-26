from typing import Literal

from pydantic import BaseModel, ConfigDict


class ConversationMessageCreate(BaseModel):
    content: str
    role: Literal["user", "assistant", "system"] = "user"


class ConversationMessageResponse(BaseModel):
    id: int
    organization_id: int
    conversation_id: int
    role: str
    content: str

    model_config = ConfigDict(from_attributes=True)


ConversationMessageRead = ConversationMessageResponse
