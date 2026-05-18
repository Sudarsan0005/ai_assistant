"""
Retrieval service with citation tracking.
"""
from dataclasses import dataclass
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from services.embedding_service import EmbeddingService
from services.vector_store import QdrantVectorStore
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """Retrieved chunk with complete source metadata."""

    chunk_id: str
    text: str
    doc_id: str
    doc_name: str
    filename: str
    file_type: str
    page_number: int
    chunk_index: int
    doc_type: str
    position: Dict[str, Any]
    metadata: Dict[str, Any]
    document_metadata: Dict[str, Any]
    similarity_score: float
    citation_id: int
    parent_chunk_id: Optional[str] = None
    image_id: Optional[str] = None


class RetrievalService:
    """Handles retrieval and retrieval-time context shaping."""

    def __init__(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: EmbeddingService,
        top_k: int = 10,
        similarity_threshold: float = 0.3,
        vector_weight: float = 0.75,
        keyword_weight: float = 0.25,
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
        use_hybrid: bool = True,
    ) -> List[RetrievedChunk]:
        """Retrieve relevant chunks for a query."""
        query_vector = self.embedding_service.encode_query(query)
        filters = {"doc_ids": doc_ids} if doc_ids else {}

        if use_hybrid:
            results = self.vector_store.hybrid_search(
                query_vector=query_vector,
                query_text=query,
                top_k=self.top_k,
                vector_weight=self.vector_weight,
                keyword_weight=self.keyword_weight,
                filters=filters,
                candidate_multiplier=settings.HYBRID_CANDIDATE_MULTIPLIER,
            )
            score_key = "hybrid_score"
        else:
            results = self.vector_store.search(
                query_vector=query_vector,
                top_k=self.top_k,
                filters=filters,
            )
            score_key = "similarity"

        filtered_results = [
            result for result in results if result.get(score_key, 0.0) >= self.similarity_threshold
        ]

        chunks: List[RetrievedChunk] = []
        for idx, result in enumerate(filtered_results):
            chunks.append(
                RetrievedChunk(
                    chunk_id=result["chunk_id"],
                    text=result["text"],
                    doc_id=result["doc_id"],
                    doc_name=result["doc_name"],
                    filename=result.get("filename") or result["doc_name"],
                    file_type=result.get("file_type") or "unknown",
                    page_number=result["page_number"],
                    chunk_index=result["chunk_index"],
                    doc_type=result["doc_type"],
                    position=result.get("position") or {},
                    metadata=result.get("metadata") or {},
                    document_metadata=result.get("document_metadata") or {},
                    similarity_score=result.get(score_key, 0.0),
                    citation_id=idx,
                    parent_chunk_id=result.get("parent_chunk_id"),
                    image_id=result.get("image_id"),
                )
            )

        logger.info("Retrieved %s chunks for query", len(chunks))
        return chunks

    def format_context(
        self,
        chunks: List[RetrievedChunk],
        include_metadata: bool = True,
    ) -> str:
        """Format chunks into the LLM context."""
        context_parts: List[str] = []
        for chunk in chunks:
            block = f"[{chunk.citation_id}] {chunk.text}"
            if include_metadata:
                meta = [
                    f"Document: {chunk.filename}",
                    f"Page: {chunk.page_number}",
                    f"Chunk: {chunk.chunk_index}",
                    f"Type: {chunk.doc_type}",
                ]
                if chunk.image_id:
                    meta.append(f"Image ID: {chunk.image_id}")
                block += f"\n({' | '.join(meta)})"
            context_parts.append(block)
        return "\n\n".join(context_parts)

    def get_citation_map(self, chunks: List[RetrievedChunk]) -> Dict[int, Dict[str, Any]]:
        """Map citation ids to source metadata."""
        return {
            chunk.citation_id: {
                "doc_id": chunk.doc_id,
                "doc_name": chunk.doc_name,
                "filename": chunk.filename,
                "file_type": chunk.file_type,
                "page_number": chunk.page_number,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "doc_type": chunk.doc_type,
                "position": chunk.position,
                "text": chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
            }
            for chunk in chunks
        }


class CitationManager:
    """Insert source citations into generated answers."""

    def __init__(self, citation_threshold: float = 0.63):
        self.citation_threshold = citation_threshold

    def insert_citations(
        self,
        answer: str,
        context_chunks: List[RetrievedChunk],
        max_citations_per_sentence: int = 4,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Insert citations into the answer."""
        sentences = self._split_into_sentences(answer)
        cited_sentences: List[str] = []
        all_citations: List[Dict[str, Any]] = []

        for sentence in sentences:
            if not sentence.strip():
                continue

            matches = self._find_matching_chunks(
                sentence,
                context_chunks,
                max_matches=max_citations_per_sentence,
            )

            if matches:
                citation_ids = [match["citation_id"] for match in matches]
                cited_sentences.append(f"{sentence} {self._format_citation_ids(citation_ids)}")
                all_citations.extend(matches)
            else:
                cited_sentences.append(sentence)

        return " ".join(cited_sentences), self._deduplicate_citations(all_citations)

    def format_references(self, citations: List[Dict[str, Any]]) -> str:
        """Format references block."""
        if not citations:
            return ""

        lines = ["References:"]
        for citation in citations:
            lines.append(
                f"[{citation['citation_id']}] {citation['doc_name']} - "
                f"page {citation['page_number']}"
            )
        return "\n".join(lines)

    def _split_into_sentences(self, text: str) -> List[str]:
        text = re.sub(r"\b(Dr|Mr|Mrs|Ms|Prof)\. ", r"\1<DOT> ", text)
        sentences = re.split(r"[.!?]+\s+", text)
        return [sentence.replace("<DOT>", ".").strip() for sentence in sentences if sentence.strip()]

    def _find_matching_chunks(
        self,
        sentence: str,
        chunks: List[RetrievedChunk],
        max_matches: int = 4,
    ) -> List[Dict[str, Any]]:
        """Find chunks that best support a sentence."""
        sentence_words = set(sentence.lower().split())
        matches: List[Dict[str, Any]] = []

        for chunk in chunks:
            chunk_words = set(chunk.text.lower().split())
            if not sentence_words:
                continue

            similarity = len(sentence_words & chunk_words) / len(sentence_words)
            if similarity < self.citation_threshold:
                continue

            matches.append(
                {
                    "citation_id": chunk.citation_id,
                    "doc_name": chunk.doc_name,
                    "page_number": chunk.page_number,
                    "similarity": similarity,
                }
            )

        matches.sort(key=lambda item: item["similarity"], reverse=True)
        return matches[:max_matches]

    def _format_citation_ids(self, citation_ids: List[int]) -> str:
        return " ".join(f"[{citation_id}]" for citation_id in sorted(set(citation_ids)))

    def _deduplicate_citations(self, citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: Dict[int, Dict[str, Any]] = {}
        for citation in citations:
            existing = unique.get(citation["citation_id"])
            if not existing or citation["similarity"] > existing["similarity"]:
                unique[citation["citation_id"]] = citation
        return list(sorted(unique.values(), key=lambda item: item["citation_id"]))
