from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    session_id: str
    filename: str
    pages: int
    chunks: int


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    question: str = Field(min_length=2, max_length=2000)


class Source(BaseModel):
    page: int
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


class HealthResponse(BaseModel):
    status: str
    api_key_configured: bool
