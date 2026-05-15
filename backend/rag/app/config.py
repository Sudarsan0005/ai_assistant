"""
Application Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Advanced RAG System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Milvus Configuration
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_DB_NAME: str = "rag_database"
    MILVUS_COLLECTION_NAME: str = "document_chunks"
    
    # Embedding Configuration
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_BATCH_SIZE: int = 32
    
    # Chunking Configuration
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    
    # Retrieval Configuration
    TOP_K: int = 10
    SIMILARITY_THRESHOLD: float = 0.3
    VECTOR_WEIGHT: float = 0.7
    KEYWORD_WEIGHT: float = 0.3
    
    # LLM Configuration
    LLM_PROVIDER: str = "openai"  # openai, anthropic, litellm
    LLM_MODEL: str = "gpt-4"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2000
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    
    # Vision Processing
    ENABLE_VISION: bool = True
    OCR_LANGUAGE: str = "en"
    VISION_MODEL: str = "paddleocr"
    
    # Citation Configuration
    CITATION_THRESHOLD: float = 0.63
    MAX_CITATIONS_PER_SENTENCE: int = 4
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
