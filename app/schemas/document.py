import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    title: str
    chunk_count: int
    created_at: datetime.datetime


class UploadResponse(BaseModel):
    document_id: int
    filename: str
    title: str
    chunk_count: int
    message: str = "Document uploaded and indexed successfully"
