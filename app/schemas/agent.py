from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    thread_id: str | None = Field(
        default=None,
        description="Conversation thread ID for memory continuity. "
        "If omitted, a new thread is created.",
    )


class ChatResponse(BaseModel):
    thread_id: str
    response: str
    contains_personal_data: bool = False
