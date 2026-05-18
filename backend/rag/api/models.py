"""
API request and response models.
"""
from typing import List, Optional

from pydantic import BaseModel


class QueryRequest(BaseModel):
    """Query request model."""

    question: str
    doc_ids: Optional[List[str]] = None
    use_citations: bool = True


class QueryResponse(BaseModel):
    """Query response model."""

    query: str
    answer: str
    answer_with_citations: str
    citations: List[dict]
    references: str
    retrieved_chunks: int
    model_used: str
    tokens_used: int


class DocumentResponse(BaseModel):
    """Document response model."""

    doc_id: str
    filename: str
    total_chunks: int
    status: str


class DocumentUploadResponse(BaseModel):
    """Document upload response."""

    doc_id: str
    filename: str
    file_size: int
    total_chunks: int
    status: str
    message: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    vector_store: str
    vector_store_connected: bool
    collection_initialized: bool
    llm_provider: str


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: str
    status_code: int
