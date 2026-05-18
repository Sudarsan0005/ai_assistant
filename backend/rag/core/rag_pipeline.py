"""
Main RAG pipeline.
"""
from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from app.config import settings
from services.chunking import get_chunker
from services.document_parser import DocumentParser
from services.embedding_service import EmbeddingService
from services.llm_service import LLMService, PromptTemplates
from services.retrieval_service import CitationManager, RetrievalService
from services.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """Ingestion response metadata."""

    doc_id: str
    filename: str
    file_path: str
    total_chunks: int
    status: str


@dataclass
class RAGResponse:
    """RAG query response."""

    query: str
    answer: str
    answer_with_citations: str
    citations: List[Dict[str, Any]]
    references: str
    retrieved_chunks: int
    model_used: str
    tokens_used: int


class RAGPipeline:
    """End-to-end ingestion and retrieval pipeline."""

    def __init__(
        self,
        qdrant_url: str = settings.QDRANT_URL,
        embedding_model: str = settings.EMBEDDING_MODEL,
        llm_provider: str = settings.LLM_PROVIDER,
        llm_model: str = settings.LLM_MODEL,
        enable_vision: bool = settings.ENABLE_VISION,
    ):
        logger.info("Initializing RAG pipeline with Qdrant storage")

        self.embedding_service = EmbeddingService(
            model_name=embedding_model,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        self.vector_store = QdrantVectorStore(
            url=qdrant_url,
            api_key=settings.QDRANT_API_KEY,
            collection_name=settings.QDRANT_COLLECTION_NAME,
            dim=self.embedding_service.get_dimension(),
            prefer_grpc=settings.QDRANT_PREFER_GRPC,
        )
        self.document_parser = DocumentParser(
            enable_vision=enable_vision,
            ocr_lang=settings.OCR_LANGUAGE,
        )
        self.retrieval_service = RetrievalService(
            vector_store=self.vector_store,
            embedding_service=self.embedding_service,
            top_k=settings.TOP_K,
            similarity_threshold=settings.SIMILARITY_THRESHOLD,
            vector_weight=settings.VECTOR_WEIGHT,
            keyword_weight=settings.KEYWORD_WEIGHT,
        )
        self.citation_manager = CitationManager(
            citation_threshold=settings.CITATION_THRESHOLD
        )
        self.llm_service = LLMService(
            provider=llm_provider,
            model=llm_model,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )

        logger.info("RAG pipeline initialized successfully")

    def ingest_document(
        self,
        file_path: str,
        filename: str,
        chunking_strategy: str = "token",
        doc_id: Optional[str] = None,
    ) -> DocumentMetadata:
        """Parse, chunk, embed, and index a document."""
        target_doc_id = doc_id or str(uuid.uuid4())

        try:
            logger.info("Starting ingestion for %s", filename)
            file_size = os.path.getsize(file_path)
            file_type = Path(filename).suffix.lstrip(".").lower()

            sections = self.document_parser.parse(file_path, filename)
            total_pages = max((section.page_number for section in sections), default=0)

            chunker = get_chunker(
                strategy=chunking_strategy,
                chunk_size=settings.CHUNK_SIZE,
                overlap=settings.CHUNK_OVERLAP,
            )
            chunks = chunker.chunk_sections(sections, target_doc_id, filename)
            embeddings = self.embedding_service.encode_texts([chunk.text for chunk in chunks])

            document_metadata = {
                "doc_id": target_doc_id,
                "filename": filename,
                "file_path": file_path,
                "file_size": file_size,
                "file_type": file_type,
                "total_chunks": len(chunks),
                "total_pages": total_pages,
                "chunking_strategy": chunking_strategy,
                "status": "completed",
                "metadata": {
                    "sections_parsed": len(sections),
                    "embedding_model": settings.EMBEDDING_MODEL,
                },
            }

            self.vector_store.insert_chunks(
                chunks=chunks,
                vectors=embeddings,
                document_metadata=document_metadata,
            )

            return DocumentMetadata(
                doc_id=target_doc_id,
                filename=filename,
                file_path=file_path,
                total_chunks=len(chunks),
                status="completed",
            )
        except Exception as exc:
            logger.error("Document ingestion failed for %s: %s", filename, exc)
            raise

    def query(
        self,
        question: str,
        doc_ids: Optional[List[str]] = None,
        use_citations: bool = True,
        custom_system_prompt: Optional[str] = None,
    ) -> RAGResponse:
        """Retrieve chunks and generate an answer."""
        logger.info("Processing query: %s", question)

        retrieved_chunks = self.retrieval_service.retrieve(
            query=question,
            doc_ids=doc_ids,
            use_hybrid=True,
        )
        if not retrieved_chunks:
            return RAGResponse(
                query=question,
                answer="I couldn't find any relevant information to answer your question.",
                answer_with_citations="",
                citations=[],
                references="",
                retrieved_chunks=0,
                model_used=self.llm_service.model,
                tokens_used=0,
            )

        context = self.retrieval_service.format_context(retrieved_chunks)
        llm_response = self.llm_service.generate_answer(
            query=question,
            context=context,
            system_prompt=custom_system_prompt or PromptTemplates.citation_aware_prompt(),
        )

        if use_citations:
            answer_with_citations, citations = self.citation_manager.insert_citations(
                answer=llm_response.answer,
                context_chunks=retrieved_chunks,
                max_citations_per_sentence=settings.MAX_CITATIONS_PER_SENTENCE,
            )
            references = self.citation_manager.format_references(citations)
        else:
            answer_with_citations = llm_response.answer
            citations = []
            references = ""

        return RAGResponse(
            query=question,
            answer=llm_response.answer,
            answer_with_citations=answer_with_citations,
            citations=citations,
            references=references,
            retrieved_chunks=len(retrieved_chunks),
            model_used=llm_response.model,
            tokens_used=llm_response.tokens_used,
        )

    def delete_document(self, doc_id: str) -> None:
        """Delete a document from the vector store."""
        self.vector_store.delete_by_doc_id(doc_id)

    def replace_document(
        self,
        doc_id: str,
        file_path: str,
        filename: str,
        chunking_strategy: str = "token",
    ) -> DocumentMetadata:
        """
        Replace an existing document while keeping the same logical document id.

        The new document is fully parsed, chunked, and embedded before the old
        chunks are deleted so a failed replacement does not wipe the existing
        document.
        """
        existing = self.get_document_info(doc_id)
        if not existing:
            raise ValueError("Document not found")

        logger.info("Replacing document %s with file %s", doc_id, filename)

        file_size = os.path.getsize(file_path)
        file_type = Path(filename).suffix.lstrip(".").lower()
        sections = self.document_parser.parse(file_path, filename)
        total_pages = max((section.page_number for section in sections), default=0)

        chunker = get_chunker(
            strategy=chunking_strategy,
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )
        chunks = chunker.chunk_sections(sections, doc_id, filename)
        embeddings = self.embedding_service.encode_texts([chunk.text for chunk in chunks])

        document_metadata = {
            "doc_id": doc_id,
            "filename": filename,
            "file_path": file_path,
            "file_size": file_size,
            "file_type": file_type,
            "total_chunks": len(chunks),
            "total_pages": total_pages,
            "chunking_strategy": chunking_strategy,
            "status": "completed",
            "created_at": existing.get("created_at"),
            "metadata": {
                "sections_parsed": len(sections),
                "embedding_model": settings.EMBEDDING_MODEL,
                "replaced": True,
            },
        }

        self.vector_store.delete_by_doc_id(doc_id)
        self.vector_store.insert_chunks(
            chunks=chunks,
            vectors=embeddings,
            document_metadata=document_metadata,
        )

        return DocumentMetadata(
            doc_id=doc_id,
            filename=filename,
            file_path=file_path,
            total_chunks=len(chunks),
            status="completed",
        )

    def get_document_info(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata."""
        return self.vector_store.get_document_metadata(doc_id)

    def list_documents(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List documents."""
        return self.vector_store.list_documents(status=status)

    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a document."""
        return self.vector_store.get_document_chunks(doc_id)

    def get_document_stats(self, doc_id: str) -> Dict[str, Any]:
        """Get document statistics."""
        return self.vector_store.get_document_stats(doc_id)

    def close(self) -> None:
        """Close downstream resources."""
        self.vector_store.close()
        logger.info("RAG pipeline closed")
