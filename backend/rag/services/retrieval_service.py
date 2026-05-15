"""
Retrieval Service with Citation Tracking
Handles document retrieval and citation management
"""
from typing import List, Dict, Any, Optional, Tuple
import json
import re
import logging
from dataclasses import dataclass

import numpy as np

from services.vector_store import MilvusVectorStore
from services.embedding_service import EmbeddingService
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """Retrieved chunk with citation info"""
    chunk_id: str
    text: str
    doc_id: str
    doc_name: str
    page_number: int
    chunk_index: int
    doc_type: str
    position: Dict[str, float]
    metadata: Dict[str, Any]
    similarity_score: float
    citation_id: int
    parent_chunk_id: Optional[str] = None
    image_id: Optional[str] = None


class RetrievalService:
    """Handles document retrieval with citation tracking"""
    
    def __init__(
        self,
        vector_store: MilvusVectorStore,
        embedding_service: EmbeddingService,
        top_k: int = 10,
        similarity_threshold: float = 0.3,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ):
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
    
    def retrieve(
        self,
        query: str,
        doc_ids: Optional[List[str]] = None,
        use_hybrid: bool = True
    ) -> List[RetrievedChunk]:
        """Retrieve relevant chunks for a query"""
        # Encode query
        query_vector = self.embedding_service.encode_query(query)
        
        # Build filters
        filters = {}
        if doc_ids:
            filters["doc_ids"] = doc_ids
        
        # Retrieve chunks
        if use_hybrid:
            results = self.vector_store.hybrid_search(
                query_vector=query_vector,
                query_text=query,
                top_k=self.top_k,
                vector_weight=self.vector_weight,
                keyword_weight=self.keyword_weight,
                filters=filters
            )
        else:
            results = self.vector_store.search(
                query_vector=query_vector,
                top_k=self.top_k,
                filters=filters
            )
        
        # Filter by similarity threshold
        filtered_results = [
            r for r in results 
            if r.get("similarity", r.get("hybrid_score", 0)) >= self.similarity_threshold
        ]
        
        # Convert to RetrievedChunk with citation IDs
        retrieved_chunks = []
        for idx, result in enumerate(filtered_results):
            # Parse JSON fields
            position = json.loads(result.get("position", "{}"))
            metadata = json.loads(result.get("metadata", "{}"))
            
            chunk = RetrievedChunk(
                chunk_id=result["chunk_id"],
                text=result["text"],
                doc_id=result["doc_id"],
                doc_name=result["doc_name"],
                page_number=result["page_number"],
                chunk_index=result["chunk_index"],
                doc_type=result["doc_type"],
                position=position,
                metadata=metadata,
                similarity_score=result.get("similarity", result.get("hybrid_score", 0)),
                citation_id=idx,
                parent_chunk_id=result.get("parent_chunk_id"),
                image_id=result.get("image_id")
            )
            retrieved_chunks.append(chunk)
        
        logger.info(f"Retrieved {len(retrieved_chunks)} chunks for query")
        return retrieved_chunks
    
    def format_context(
        self,
        chunks: List[RetrievedChunk],
        include_metadata: bool = True
    ) -> str:
        """Format retrieved chunks as context for LLM"""
        context_parts = []
        
        for chunk in chunks:
            # Format chunk with citation marker
            chunk_text = f"[{chunk.citation_id}] {chunk.text}"
            
            if include_metadata:
                # Add metadata
                meta_parts = [
                    f"Document: {chunk.doc_name}",
                    f"Page: {chunk.page_number}",
                    f"Type: {chunk.doc_type}"
                ]
                
                if chunk.image_id:
                    meta_parts.append(f"Image ID: {chunk.image_id}")
                
                metadata_str = " | ".join(meta_parts)
                chunk_text += f"\n({metadata_str})"
            
            context_parts.append(chunk_text)
        
        return "\n\n".join(context_parts)
    
    def get_citation_map(self, chunks: List[RetrievedChunk]) -> Dict[int, Dict[str, Any]]:
        """Create a map of citation IDs to chunk metadata"""
        citation_map = {}
        
        for chunk in chunks:
            citation_map[chunk.citation_id] = {
                "doc_name": chunk.doc_name,
                "page_number": chunk.page_number,
                "chunk_id": chunk.chunk_id,
                "doc_type": chunk.doc_type,
                "position": chunk.position,
                "text": chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text
            }
        
        return citation_map


class CitationManager:
    """Manages citation insertion and tracking in generated answers"""
    
    def __init__(self, citation_threshold: float = 0.63):
        self.citation_threshold = citation_threshold
    
    def insert_citations(
        self,
        answer: str,
        context_chunks: List[RetrievedChunk],
        max_citations_per_sentence: int = 4
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Insert citations into answer based on chunk similarity"""
        # Split answer into sentences
        sentences = self._split_into_sentences(answer)
        
        # For each sentence, find best matching chunks
        cited_sentences = []
        all_citations = []
        
        for sentence in sentences:
            if not sentence.strip():
                continue
            
            # Find matching chunks for this sentence
            matches = self._find_matching_chunks(
                sentence,
                context_chunks,
                max_matches=max_citations_per_sentence
            )
            
            if matches:
                # Add citations to sentence
                citation_ids = [m["citation_id"] for m in matches]
                citation_str = self._format_citation_ids(citation_ids)
                cited_sentence = f"{sentence} {citation_str}"
                cited_sentences.append(cited_sentence)
                
                # Track citations
                for match in matches:
                    all_citations.append({
                        "citation_id": match["citation_id"],
                        "doc_name": match["doc_name"],
                        "page_number": match["page_number"],
                        "similarity": match["similarity"]
                    })
            else:
                # No citation for this sentence
                cited_sentences.append(sentence)
        
        # Combine sentences
        cited_answer = " ".join(cited_sentences)
        
        # Deduplicate citations
        unique_citations = self._deduplicate_citations(all_citations)
        
        return cited_answer, unique_citations
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Handle common abbreviations
        text = re.sub(r'\b(Dr|Mr|Mrs|Ms|Prof)\. ', r'\1<DOT> ', text)
        
        # Split by sentence boundaries
        sentences = re.split(r'[.!?]+\s+', text)
        
        # Restore abbreviations
        sentences = [s.replace('<DOT>', '.') for s in sentences]
        
        return [s.strip() for s in sentences if s.strip()]
    
    def _find_matching_chunks(
        self,
        sentence: str,
        chunks: List[RetrievedChunk],
        max_matches: int = 4
    ) -> List[Dict[str, Any]]:
        """Find chunks that match a sentence"""
        matches = []
        sentence_lower = sentence.lower()
        sentence_words = set(sentence_lower.split())
        
        for chunk in chunks:
            # Calculate word overlap similarity
            chunk_words = set(chunk.text.lower().split())
            overlap = len(sentence_words & chunk_words)
            
            if len(sentence_words) == 0:
                continue
            
            similarity = overlap / len(sentence_words)
            
            # Check if similarity exceeds threshold
            if similarity >= self.citation_threshold:
                matches.append({
                    "citation_id": chunk.citation_id,
                    "doc_name": chunk.doc_name,
                    "page_number": chunk.page_number,
                    "chunk_id": chunk.chunk_id,
                    "similarity": similarity
                })
        
        # Sort by similarity and take top matches
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches[:max_matches]
    
    def _format_citation_ids(self, citation_ids: List[int]) -> str:
        """Format citation IDs as superscript notation"""
        if not citation_ids:
            return ""
        
        # Remove duplicates and sort
        unique_ids = sorted(set(citation_ids))
        
        # Format as [1,2,3] or [1-3]
        if len(unique_ids) == 1:
            return f"[{unique_ids[0]}]"
        else:
            # Check if consecutive
            is_consecutive = all(
                unique_ids[i] + 1 == unique_ids[i + 1] 
                for i in range(len(unique_ids) - 1)
            )
            
            if is_consecutive and len(unique_ids) > 2:
                return f"[{unique_ids[0]}-{unique_ids[-1]}]"
            else:
                return f"[{','.join(map(str, unique_ids))}]"
    
    def _deduplicate_citations(
        self,
        citations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate citations"""
        seen = set()
        unique = []
        
        for citation in citations:
            key = (citation["citation_id"], citation["doc_name"], citation["page_number"])
            if key not in seen:
                seen.add(key)
                unique.append(citation)
        
        return unique
    
    def format_references(
        self,
        citations: List[Dict[str, Any]]
    ) -> str:
        """Format citations as reference list"""
        if not citations:
            return ""
        
        # Group by document
        doc_citations = {}
        for citation in citations:
            key = citation["doc_name"]
            if key not in doc_citations:
                doc_citations[key] = []
            doc_citations[key].append(citation)
        
        # Format references
        references = ["**References:**\n"]
        
        for doc_name, doc_cites in doc_citations.items():
            pages = sorted(set(c["page_number"] for c in doc_cites))
            page_str = ", ".join(map(str, pages))
            
            citation_ids = sorted(set(c["citation_id"] for c in doc_cites))
            id_str = ", ".join(map(str, citation_ids))
            
            references.append(f"[{id_str}] {doc_name} (Pages: {page_str})")
        
        return "\n".join(references)
