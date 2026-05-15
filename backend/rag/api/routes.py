"""
API Routes
"""
import os
import shutil
from typing import List
from pathlib import Path
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from fastapi.responses import JSONResponse

from api.models import (
    QueryRequest, QueryResponse, DocumentResponse,
    DocumentUploadResponse, HealthResponse, ErrorResponse
)
from core.rag_pipeline import RAGPipeline
from app.config import settings

logger = logging.getLogger(__name__)

# Create routers
health_router = APIRouter(prefix="", tags=["Health"])
document_router = APIRouter(prefix="/documents", tags=["Documents"])
query_router = APIRouter(prefix="/query", tags=["Query"])

# Upload directory
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# Dependency to get RAG pipeline
def get_rag_pipeline() -> RAGPipeline:
    """Get RAG pipeline instance"""
    from app.main import rag_pipeline
    if rag_pipeline is None:
        raise HTTPException(status_code=500, detail="RAG pipeline not initialized")
    return rag_pipeline


@health_router.get("/", response_model=HealthResponse)
async def health_check(pipeline: RAGPipeline = Depends(get_rag_pipeline)):
    """Health check endpoint"""
    try:
        # Check if Milvus is connected
        milvus_connected = pipeline.vector_store.collection is not None
        
        return HealthResponse(
            status="healthy",
            version=settings.APP_VERSION,
            milvus_connected=milvus_connected,
            collections_initialized=True
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            version=settings.APP_VERSION,
            milvus_connected=False,
            collections_initialized=False
        )


@document_router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    chunking_strategy: str = Query("token", enum=["token", "semantic", "hierarchical"]),
    pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    Upload and ingest a document
    
    Supports: PDF, DOCX, TXT, MD, images (PNG, JPG, JPEG)
    """
    try:
        # Save uploaded file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        file_size = os.path.getsize(file_path)
        logger.info(f"Uploaded file: {file.filename} ({file_size} bytes)")
        
        # Ingest document
        doc_metadata = pipeline.ingest_document(
            file_path=str(file_path),
            filename=file.filename,
            chunking_strategy=chunking_strategy
        )
        
        return DocumentUploadResponse(
            doc_id=doc_metadata.doc_id,
            filename=doc_metadata.filename,
            file_size=file_size,
            total_chunks=doc_metadata.total_chunks,
            status=doc_metadata.status,
            message=f"Document processed successfully with {doc_metadata.total_chunks} chunks"
        )
    
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        file.file.close()


@query_router.post("", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    Query the RAG system
    
    Retrieves relevant documents and generates an answer with citations
    """
    try:
        response = pipeline.query(
            question=request.question,
            doc_ids=request.doc_ids,
            use_citations=request.use_citations
        )
        
        return QueryResponse(
            query=response.query,
            answer=response.answer,
            answer_with_citations=response.answer_with_citations,
            citations=response.citations,
            references=response.references,
            retrieved_chunks=response.retrieved_chunks,
            model_used=response.model_used,
            tokens_used=response.tokens_used
        )
    
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@document_router.get("", response_model=List[DocumentResponse])
async def list_documents(
    status: Optional[str] = Query(None),
    pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """List all documents in the system"""
    try:
        documents = pipeline.list_documents(status=status)
        return [
            DocumentResponse(
                doc_id=doc.get("doc_id"),
                filename=doc.get("filename"),
                total_chunks=doc.get("total_chunks"),
                status=doc.get("status")
            )
            for doc in documents
        ]
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@document_router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """Get document information"""
    try:
        doc = pipeline.get_document_info(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return DocumentResponse(
            doc_id=doc.get("doc_id"),
            filename=doc.get("filename"),
            total_chunks=doc.get("total_chunks"),
            status=doc.get("status")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@document_router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """Delete a document"""
    try:
        pipeline.delete_document(doc_id)
        return {"message": "Document deleted successfully", "doc_id": doc_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@document_router.get("/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """Get all chunks for a document"""
    try:
        chunks = pipeline.get_document_chunks(doc_id)
        return {"doc_id": doc_id, "chunks": chunks, "total": len(chunks)}
    except Exception as e:
        logger.error(f"Failed to get chunks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@document_router.get("/{doc_id}/stats")
async def get_document_stats(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """Get document statistics"""
    try:
        stats = pipeline.get_document_stats(doc_id)
        if not stats:
            raise HTTPException(status_code=404, detail="Document not found")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
