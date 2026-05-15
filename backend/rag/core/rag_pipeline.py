"""
Main RAG Pipeline - Using Milvus for ALL storage
No separate database needed - everything in Milvus
"""
import os
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from dataclasses import dataclass, asdict

from services.document_parser import DocumentParser, ParsedSection
from services.chunking import get_chunker, Chunk
from services.vector_store import MilvusVectorStore
from services.embedding_service import EmbeddingService
from services.retrieval_service import RetrievalService, CitationManager, RetrievedChunk
from services.llm_service import LLMService, PromptTemplates
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """Document metadata"""
    doc_id: str
    filename: str
    file_path: str
    total_chunks: int
    status: str  # processing, completed, failed


@dataclass
class RAGResponse:
    """RAG query response"""
    query: str
    answer: str
    answer_with_citations: str
    citations: List[Dict[str, Any]]
    references: str
    retrieved_chunks: int
    model_used: str
    tokens_used: int


class RAGPipeline:
    """
    Complete RAG pipeline using ONLY Milvus for storage
    All metadata stored in Milvus - no separate database needed
    """
    
    def __init__(
        self,
        milvus_host: str = settings.MILVUS_HOST,
        milvus_port: int = settings.MILVUS_PORT,
        embedding_model: str = settings.EMBEDDING_MODEL,
        llm_provider: str = settings.LLM_PROVIDER,
        llm_model: str = settings.LLM_MODEL,
        enable_vision: bool = settings.ENABLE_VISION
    ):
        logger.info("Initializing RAG Pipeline with Milvus-only storage...")
        
        # Initialize embedding service
        self.embedding_service = EmbeddingService(
            model_name=embedding_model,
            batch_size=settings.EMBEDDING_BATCH_SIZE
        )
        
        # Initialize vector store (now handles ALL metadata)
        self.vector_store = MilvusVectorStore(
            host=milvus_host,
            port=milvus_port,
            collection_name=settings.MILVUS_COLLECTION_NAME,
            dim=self.embedding_service.get_dimension()
        )
        
        # Initialize document parser
        self.document_parser = DocumentParser(
            enable_vision=enable_vision,
            ocr_lang=settings.OCR_LANGUAGE
        )
        
        # Initialize retrieval service
        self.retrieval_service = RetrievalService(
            vector_store=self.vector_store,
            embedding_service=self.embedding_service,
            top_k=settings.TOP_K,
            similarity_threshold=settings.SIMILARITY_THRESHOLD,
            vector_weight=settings.VECTOR_WEIGHT,
            keyword_weight=settings.KEYWORD_WEIGHT
        )
        
        # Initialize citation manager
        self.citation_manager = CitationManager(
            citation_threshold=settings.CITATION_THRESHOLD
        )
        
        # Initialize LLM service
        self.llm_service = LLMService(
            provider=llm_provider,
            model=llm_model,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS
        )
        
        logger.info("RAG Pipeline initialized successfully (Milvus-only architecture)")
    
    def ingest_document(
        self,
        file_path: str,
        filename: str,
        chunking_strategy: str = "token"
    ) -> DocumentMetadata:
        """
        Ingest a document into the RAG system
        All metadata stored in Milvus
        
        Steps:
        1. Parse document (with vision if enabled)
        2. Chunk the parsed sections
        3. Generate embeddings
        4. Store chunks in Milvus (with vectors)
        5. Store document metadata in Milvus
        """
        doc_id = str(uuid.uuid4())
        
        try:
            logger.info(f"Starting ingestion for: {filename}")
            
            # Get file info
            file_size = os.path.getsize(file_path)
            file_type = Path(filename).suffix.lstrip('.')
            
            # Step 1: Parse document
            logger.info("Parsing document...")
            sections = self.document_parser.parse(file_path, filename)
            logger.info(f"Parsed {len(sections)} sections")
            
            # Calculate total pages
            total_pages = max([s.page_number for s in sections]) if sections else 0
            
            # Step 2: Chunk sections
            logger.info("Chunking sections...")
            chunker = get_chunker(
                strategy=chunking_strategy,
                chunk_size=settings.CHUNK_SIZE,
                overlap=settings.CHUNK_OVERLAP
            )
            chunks = chunker.chunk_sections(sections, doc_id, filename)
            logger.info(f"Created {len(chunks)} chunks")
            
            # Step 3: Generate embeddings
            logger.info("Generating embeddings...")
            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = self.embedding_service.encode_texts(chunk_texts)
            logger.info(f"Generated {len(embeddings)} embeddings")
            
            # Step 4: Store chunks in Milvus
            logger.info("Storing chunks in Milvus...")
            self.vector_store.insert_chunks(chunks, embeddings)
            logger.info("Chunks stored")
            
            # Step 5: Store document metadata in Milvus
            logger.info("Storing document metadata in Milvus...")
            self.vector_store.insert_document_metadata(
                doc_id=doc_id,
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                file_type=file_type,
                total_chunks=len(chunks),
                total_pages=total_pages,
                chunking_strategy=chunking_strategy,
                metadata={
                    "sections_parsed": len(sections),
                    "embedding_model": settings.EMBEDDING_MODEL
                }
            )
            logger.info("Document metadata stored")
            
            # Create metadata object
            doc_metadata = DocumentMetadata(
                doc_id=doc_id,
                filename=filename,
                file_path=file_path,
                total_chunks=len(chunks),
                status="completed"
            )
            
            logger.info(f"Document ingestion completed: {doc_id}")
            return doc_metadata
        
        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            # Store failed document metadata
            try:
                self.vector_store.insert_document_metadata(
                    doc_id=doc_id,
                    filename=filename,
                    file_path=file_path,
                    file_size=0,
                    file_type=Path(filename).suffix.lstrip('.'),
                    total_chunks=0,
                    total_pages=0,
                    chunking_strategy=chunking_strategy,
                    metadata={"error": str(e)}
                )
            except:
                pass
            
            raise
    
    def query(
        self,
        question: str,
        doc_ids: Optional[List[str]] = None,
        use_citations: bool = True,
        custom_system_prompt: Optional[str] = None
    ) -> RAGResponse:
        """
        Query the RAG system
        
        Steps:
        1. Retrieve relevant chunks from Milvus
        2. Format context
        3. Generate answer with LLM
        4. Insert citations
        5. Format references
        """
        logger.info(f"Processing query: {question}")
        
        try:
            # Step 1: Retrieve relevant chunks
            logger.info("Retrieving relevant chunks...")
            retrieved_chunks = self.retrieval_service.retrieve(
                query=question,
                doc_ids=doc_ids,
                use_hybrid=True
            )
            logger.info(f"Retrieved {len(retrieved_chunks)} chunks")
            
            if not retrieved_chunks:
                return RAGResponse(
                    query=question,
                    answer="I couldn't find any relevant information to answer your question.",
                    answer_with_citations="",
                    citations=[],
                    references="",
                    retrieved_chunks=0,
                    model_used=self.llm_service.model,
                    tokens_used=0
                )
            
            # Step 2: Format context
            logger.info("Formatting context...")
            context = self.retrieval_service.format_context(retrieved_chunks)
            
            # Step 3: Generate answer
            logger.info("Generating answer...")
            llm_response = self.llm_service.generate_answer(
                query=question,
                context=context,
                system_prompt=custom_system_prompt or PromptTemplates.citation_aware_prompt()
            )
            logger.info("Answer generated")
            
            # Step 4: Insert citations (if enabled)
            if use_citations:
                logger.info("Inserting citations...")
                answer_with_citations, citations = self.citation_manager.insert_citations(
                    answer=llm_response.answer,
                    context_chunks=retrieved_chunks,
                    max_citations_per_sentence=settings.MAX_CITATIONS_PER_SENTENCE
                )
                
                # Step 5: Format references
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
                tokens_used=llm_response.tokens_used
            )
        
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            raise
    
    def delete_document(self, doc_id: str):
        """Delete a document from Milvus (chunks + metadata)"""
        logger.info(f"Deleting document: {doc_id}")
        self.vector_store.delete_by_doc_id(doc_id)
        logger.info("Document deleted successfully")
    
    def get_document_info(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata from Milvus"""
        return self.vector_store.get_document_metadata(doc_id)
    
    def list_documents(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all documents from Milvus"""
        return self.vector_store.list_documents(status=status)
    
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a document from Milvus"""
        chunks = self.vector_store.collection.query(
            expr=f'doc_id == "{doc_id}"',
            output_fields=["*"],
            limit=10000
        )
        return chunks
    
    def get_document_stats(self, doc_id: str) -> Dict[str, Any]:
        """Get statistics for a document"""
        return self.vector_store.get_document_stats(doc_id)
    
    def close(self):
        """Close connections"""
        self.vector_store.close()
        logger.info("RAG Pipeline closed")
