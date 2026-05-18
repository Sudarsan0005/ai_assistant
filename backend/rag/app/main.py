"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import document_router, health_router, query_router
from app.config import settings
from core.rag_pipeline import RAGPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

rag_pipeline: RAGPipeline = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifespan."""
    global rag_pipeline

    try:
        logger.info("Starting RAG application...")
        rag_pipeline = RAGPipeline(
            qdrant_url=settings.QDRANT_URL,
            embedding_model=settings.EMBEDDING_MODEL,
            llm_provider=settings.LLM_PROVIDER,
            llm_model=settings.LLM_MODEL,
            enable_vision=settings.ENABLE_VISION,
        )
        logger.info("RAG application started successfully")
    except Exception as exc:
        logger.error("Failed to start RAG application: %s", exc)
        raise

    yield

    if rag_pipeline:
        rag_pipeline.close()
        logger.info("RAG application shut down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="RAG system with Qdrant-backed retrieval and LangChain-based model routing",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(document_router)
app.include_router(query_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
