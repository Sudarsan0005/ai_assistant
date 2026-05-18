"""
API routes.
"""
import logging
import os
from pathlib import Path
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from api.models import (
    DocumentResponse,
    DocumentUploadResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
)
from app.config import settings
from core.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)

health_router = APIRouter(prefix="", tags=["Health"])
document_router = APIRouter(prefix="/documents", tags=["Documents"])
query_router = APIRouter(prefix="/query", tags=["Query"])

UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def get_rag_pipeline() -> RAGPipeline:
    """Return the process-wide pipeline."""
    from app.main import rag_pipeline

    if rag_pipeline is None:
        raise HTTPException(status_code=500, detail="RAG pipeline not initialized")
    return rag_pipeline


@health_router.get("/", response_model=HealthResponse)
async def health_check(pipeline: RAGPipeline = Depends(get_rag_pipeline)):
    """Health check endpoint."""
    connected = pipeline.vector_store.is_ready()
    return HealthResponse(
        status="healthy" if connected else "unhealthy",
        version=settings.APP_VERSION,
        vector_store="qdrant",
        vector_store_connected=connected,
        collection_initialized=connected,
        llm_provider=settings.LLM_PROVIDER,
    )


@document_router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    chunking_strategy: str = Query("token", enum=["token", "semantic", "hierarchical"]),
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """Upload and ingest a document."""
    file_path = UPLOAD_DIR / file.filename
    try:
        with open(file_path, "wb") as handle:
            shutil.copyfileobj(file.file, handle)

        file_size = os.path.getsize(file_path)
        doc_metadata = pipeline.ingest_document(
            file_path=str(file_path),
            filename=file.filename,
            chunking_strategy=chunking_strategy,
        )

        return DocumentUploadResponse(
            doc_id=doc_metadata.doc_id,
            filename=doc_metadata.filename,
            file_size=file_size,
            total_chunks=doc_metadata.total_chunks,
            status=doc_metadata.status,
            message=f"Document processed successfully with {doc_metadata.total_chunks} chunks",
        )
    except Exception as exc:
        logger.error("Upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        file.file.close()


@document_router.put("/{doc_id}", response_model=DocumentUploadResponse)
async def replace_document(
    doc_id: str,
    file: UploadFile = File(...),
    chunking_strategy: str = Query("token", enum=["token", "semantic", "hierarchical"]),
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """Replace an existing document while keeping the same document id."""
    file_path = UPLOAD_DIR / file.filename
    try:
        with open(file_path, "wb") as handle:
            shutil.copyfileobj(file.file, handle)

        file_size = os.path.getsize(file_path)
        doc_metadata = pipeline.replace_document(
            doc_id=doc_id,
            file_path=str(file_path),
            filename=file.filename,
            chunking_strategy=chunking_strategy,
        )

        return DocumentUploadResponse(
            doc_id=doc_metadata.doc_id,
            filename=doc_metadata.filename,
            file_size=file_size,
            total_chunks=doc_metadata.total_chunks,
            status=doc_metadata.status,
            message=f"Document replaced successfully with {doc_metadata.total_chunks} chunks",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Replace failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        file.file.close()


@query_router.post("", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """Query the RAG system."""
    try:
        response = pipeline.query(
            question=request.question,
            doc_ids=request.doc_ids,
            use_citations=request.use_citations,
        )
        return QueryResponse(
            query=response.query,
            answer=response.answer,
            answer_with_citations=response.answer_with_citations,
            citations=response.citations,
            references=response.references,
            retrieved_chunks=response.retrieved_chunks,
            model_used=response.model_used,
            tokens_used=response.tokens_used,
        )
    except Exception as exc:
        logger.error("Query failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@document_router.get("", response_model=list[DocumentResponse])
async def list_documents(
    status: Optional[str] = Query(None),
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """List all indexed documents."""
    try:
        documents = pipeline.list_documents(status=status)
        return [
            DocumentResponse(
                doc_id=document.get("doc_id"),
                filename=document.get("filename"),
                total_chunks=document.get("total_chunks"),
                status=document.get("status"),
            )
            for document in documents
        ]
    except Exception as exc:
        logger.error("Failed to list documents: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@document_router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """Get document information."""
    try:
        document = pipeline.get_document_info(doc_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentResponse(
            doc_id=document.get("doc_id"),
            filename=document.get("filename"),
            total_chunks=document.get("total_chunks"),
            status=document.get("status"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get document: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@document_router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """Delete a document."""
    try:
        pipeline.delete_document(doc_id)
        return {"message": "Document deleted successfully", "doc_id": doc_id}
    except Exception as exc:
        logger.error("Failed to delete document: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@document_router.get("/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """Get all chunks for a document."""
    try:
        chunks = pipeline.get_document_chunks(doc_id)
        return {"doc_id": doc_id, "chunks": chunks, "total": len(chunks)}
    except Exception as exc:
        logger.error("Failed to get chunks: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@document_router.get("/{doc_id}/stats")
async def get_document_stats(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """Get aggregated document statistics."""
    try:
        stats = pipeline.get_document_stats(doc_id)
        if not stats:
            raise HTTPException(status_code=404, detail="Document not found")
        return stats
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get document stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
