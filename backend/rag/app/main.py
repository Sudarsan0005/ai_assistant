"""
FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from api.routes import health_router, document_router, query_router
from core.rag_pipeline import RAGPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global RAG pipeline instance
rag_pipeline: RAGPipeline = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    global rag_pipeline
    
    # Startup
    try:
        logger.info("Starting RAG application...")
        rag_pipeline = RAGPipeline(
            milvus_host=settings.MILVUS_HOST,
            milvus_port=settings.MILVUS_PORT,
            embedding_model=settings.EMBEDDING_MODEL,
            llm_provider=settings.LLM_PROVIDER,
            llm_model=settings.LLM_MODEL,
            enable_vision=settings.ENABLE_VISION
        )
        logger.info("RAG application started successfully")
    except Exception as e:
        logger.error(f"Failed to start RAG application: {e}")
        raise
    
    yield
    
    # Shutdown
    if rag_pipeline:
        rag_pipeline.close()
        logger.info("RAG application shut down")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Advanced RAG System with Milvus-Only Storage and Vision Support",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(document_router)
app.include_router(query_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
