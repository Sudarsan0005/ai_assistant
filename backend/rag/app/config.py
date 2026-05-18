"""
Application configuration.
"""
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Advanced RAG System"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # Qdrant configuration
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "document_chunks"
    QDRANT_PREFER_GRPC: bool = False

    # Embedding configuration
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_BATCH_SIZE: int = 32

    # Chunking configuration
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50

    # Retrieval configuration
    TOP_K: int = 10
    SIMILARITY_THRESHOLD: float = 0.3
    VECTOR_WEIGHT: float = 0.75
    KEYWORD_WEIGHT: float = 0.25
    HYBRID_CANDIDATE_MULTIPLIER: int = 3

    # LLM configuration
    LLM_PROVIDER: str = "openai"  # openai|anthropic|ollama|nvidia|openai_compatible
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2000

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None

    ANTHROPIC_API_KEY: Optional[str] = None

    OLLAMA_BASE_URL: str = "http://localhost:11434"

    NVIDIA_API_KEY: Optional[str] = None

    OPENAI_COMPATIBLE_API_KEY: Optional[str] = None

    # Vision processing
    ENABLE_VISION: bool = True
    OCR_LANGUAGE: str = "en"
    VISION_MODEL: str = "paddleocr"

    # Citation configuration
    CITATION_THRESHOLD: float = 0.63
    MAX_CITATIONS_PER_SENTENCE: int = 4

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


settings = Settings()
