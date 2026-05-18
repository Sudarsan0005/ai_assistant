"""
Qdrant-backed vector store.

The collection stores one record per chunk and duplicates the document metadata
needed at retrieval time so a retrieved chunk is self-describing.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models

from services.chunking import Chunk

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Vector store with single-collection chunk payloads."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: Optional[str] = None,
        collection_name: str = "document_chunks",
        dim: int = 768,
        prefer_grpc: bool = False,
    ):
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.dim = dim
        self.prefer_grpc = prefer_grpc
        self.client = self._connect()
        self._create_collection()

    def _connect(self) -> QdrantClient:
        """Create a Qdrant client and validate connectivity."""
        try:
            client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                prefer_grpc=self.prefer_grpc,
            )
            client.get_collections()
            logger.info("Connected to Qdrant at %s", self.url)
            return client
        except Exception as exc:
            logger.error("Failed to connect to Qdrant: %s", exc)
            raise

    def _create_collection(self) -> None:
        """Create the chunk collection if it does not exist."""
        collections = self.client.get_collections().collections
        exists = any(item.name == self.collection_name for item in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.dim,
                    distance=models.Distance.COSINE,
                    on_disk=True,
                ),
            )
            logger.info("Created Qdrant collection: %s", self.collection_name)

        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create payload indexes used by filters and document aggregation."""
        indexes = [
            ("doc_id", models.PayloadSchemaType.KEYWORD),
            ("doc_name", models.PayloadSchemaType.KEYWORD),
            ("doc_type", models.PayloadSchemaType.KEYWORD),
            ("file_type", models.PayloadSchemaType.KEYWORD),
            ("page_number", models.PayloadSchemaType.INTEGER),
            ("chunk_index", models.PayloadSchemaType.INTEGER),
            ("status", models.PayloadSchemaType.KEYWORD),
        ]

        for field_name, schema_type in indexes:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema_type,
                )
            except Exception:
                # Index may already exist depending on Qdrant version.
                continue

    def is_ready(self) -> bool:
        """Return whether the collection is available."""
        try:
            self.client.get_collection(self.collection_name)
            return True
        except Exception:
            return False

    def insert_chunks(
        self,
        chunks: List[Chunk],
        vectors: np.ndarray,
        document_metadata: Dict[str, Any],
    ) -> List[str]:
        """Insert chunk points with full payload metadata."""
        if len(chunks) != len(vectors):
            raise ValueError("Number of chunks and vectors must match")

        inserted_ids: List[str] = []
        points: List[models.PointStruct] = []
        now = datetime.now(timezone.utc).isoformat()

        for chunk, vector in zip(chunks, vectors):
            payload = {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "doc_id": chunk.doc_id,
                "doc_name": chunk.doc_name,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "doc_type": chunk.doc_type,
                "position": chunk.position,
                "metadata": chunk.metadata,
                "parent_chunk_id": chunk.parent_chunk_id,
                "image_id": chunk.image_id,
                "filename": document_metadata["filename"],
                "file_path": document_metadata["file_path"],
                "file_size": document_metadata["file_size"],
                "file_type": document_metadata["file_type"],
                "total_chunks": document_metadata["total_chunks"],
                "total_pages": document_metadata["total_pages"],
                "chunking_strategy": document_metadata["chunking_strategy"],
                "status": document_metadata.get("status", "completed"),
                "created_at": document_metadata.get("created_at", now),
                "processed_at": document_metadata.get("processed_at", now),
                "document_metadata": document_metadata.get("metadata", {}),
            }
            inserted_ids.append(chunk.chunk_id)
            points.append(
                models.PointStruct(
                    id=chunk.chunk_id,
                    vector=vector.tolist(),
                    payload=payload,
                )
            )

        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        logger.info("Inserted %s chunks into Qdrant", len(points))
        return inserted_ids

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run vector similarity search."""
        qdrant_filter = self._build_filter(filters)
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            query_filter=qdrant_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        return [self._format_hit(hit) for hit in hits]

    def hybrid_search(
        self,
        query_vector: np.ndarray,
        query_text: str,
        top_k: int = 10,
        vector_weight: float = 0.75,
        keyword_weight: float = 0.25,
        filters: Optional[Dict[str, Any]] = None,
        candidate_multiplier: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve vector candidates and re-rank them with a lightweight keyword score.

        This keeps the storage simple while still improving precision on exact terms.
        """
        candidate_limit = max(top_k, top_k * max(candidate_multiplier, 1))
        vector_hits = self.search(query_vector, top_k=candidate_limit, filters=filters)
        query_terms = self._normalize_terms(query_text)

        reranked: List[Dict[str, Any]] = []
        for hit in vector_hits:
            text_terms = self._normalize_terms(
                f"{hit.get('text', '')} {hit.get('doc_name', '')}"
            )
            keyword_score = self._keyword_score(query_terms, text_terms)
            vector_score = float(hit.get("similarity", 0.0))
            hybrid_score = (vector_weight * vector_score) + (keyword_weight * keyword_score)
            hit["keyword_score"] = keyword_score
            hit["hybrid_score"] = hybrid_score
            reranked.append(hit)

        reranked.sort(key=lambda item: item["hybrid_score"], reverse=True)
        return reranked[:top_k]

    def get_document_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Build document metadata from chunk payloads."""
        chunks = self.get_document_chunks(doc_id)
        if not chunks:
            return None

        first = chunks[0]
        return self._aggregate_document(first, chunks)

    def list_documents(
        self,
        status: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """List documents by aggregating unique doc_ids from chunk payloads."""
        filters = {"status": status} if status else None
        points = self._scroll_all(filters=filters, limit=limit * 20)
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for point in points:
            payload = point.payload or {}
            doc_id = payload.get("doc_id")
            if doc_id:
                grouped[doc_id].append(payload)

        documents: List[Dict[str, Any]] = []
        for doc_id, payloads in grouped.items():
            documents.append(self._aggregate_document(payloads[0], payloads))

        documents.sort(key=lambda item: item.get("processed_at", ""), reverse=True)
        return documents[:limit]

    def delete_by_doc_id(self, doc_id: str) -> None:
        """Delete all chunks for a document."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_id",
                            match=models.MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
            wait=True,
        )
        logger.info("Deleted document %s from Qdrant", doc_id)

    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a document."""
        points = self._scroll_all(filters={"doc_ids": [doc_id]}, limit=10000)
        chunks = [self._payload_to_chunk_dict(point.payload or {}) for point in points]
        chunks.sort(key=lambda item: (item.get("page_number", 0), item.get("chunk_index", 0)))
        return chunks

    def get_document_stats(self, doc_id: str) -> Dict[str, Any]:
        """Return aggregated document statistics."""
        metadata = self.get_document_metadata(doc_id)
        if not metadata:
            return {}

        return {
            "doc_id": metadata["doc_id"],
            "filename": metadata["filename"],
            "total_chunks": metadata["total_chunks"],
            "total_pages": metadata["total_pages"],
            "file_type": metadata["file_type"],
            "status": metadata["status"],
            "created_at": metadata["created_at"],
            "processed_at": metadata["processed_at"],
        }

    def close(self) -> None:
        """Close the client."""
        self.client.close()

    def _build_filter(self, filters: Optional[Dict[str, Any]]) -> Optional[models.Filter]:
        """Convert app filters into a Qdrant filter."""
        if not filters:
            return None

        must: List[models.FieldCondition] = []
        if filters.get("doc_ids"):
            must.append(
                models.FieldCondition(
                    key="doc_id",
                    match=models.MatchAny(any=filters["doc_ids"]),
                )
            )
        if filters.get("doc_types"):
            must.append(
                models.FieldCondition(
                    key="doc_type",
                    match=models.MatchAny(any=filters["doc_types"]),
                )
            )
        if filters.get("page_number") is not None:
            must.append(
                models.FieldCondition(
                    key="page_number",
                    match=models.MatchValue(value=filters["page_number"]),
                )
            )
        if filters.get("status"):
            must.append(
                models.FieldCondition(
                    key="status",
                    match=models.MatchValue(value=filters["status"]),
                )
            )

        return models.Filter(must=must) if must else None

    def _format_hit(self, hit: Any) -> Dict[str, Any]:
        """Convert a Qdrant hit into the retrieval format used by the service."""
        payload = hit.payload or {}
        result = self._payload_to_chunk_dict(payload)
        result["similarity"] = float(hit.score)
        return result

    def _payload_to_chunk_dict(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize chunk payload to the API-facing dictionary."""
        return {
            "chunk_id": payload.get("chunk_id"),
            "text": payload.get("text", ""),
            "doc_id": payload.get("doc_id"),
            "doc_name": payload.get("doc_name") or payload.get("filename"),
            "page_number": payload.get("page_number", 0),
            "chunk_index": payload.get("chunk_index", 0),
            "doc_type": payload.get("doc_type", "text"),
            "position": payload.get("position") or {},
            "metadata": payload.get("metadata") or {},
            "parent_chunk_id": payload.get("parent_chunk_id"),
            "image_id": payload.get("image_id"),
            "filename": payload.get("filename"),
            "file_path": payload.get("file_path"),
            "file_size": payload.get("file_size"),
            "file_type": payload.get("file_type"),
            "total_chunks": payload.get("total_chunks"),
            "total_pages": payload.get("total_pages"),
            "chunking_strategy": payload.get("chunking_strategy"),
            "status": payload.get("status"),
            "created_at": payload.get("created_at"),
            "processed_at": payload.get("processed_at"),
            "document_metadata": payload.get("document_metadata") or {},
        }

    def _aggregate_document(
        self,
        first_payload: Dict[str, Any],
        payloads: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Aggregate document-level metadata from chunk payloads."""
        payloads_list = list(payloads)
        pages = {
            payload.get("page_number")
            for payload in payloads_list
            if payload.get("page_number") is not None
        }
        return {
            "doc_id": first_payload.get("doc_id"),
            "filename": first_payload.get("filename"),
            "file_path": first_payload.get("file_path"),
            "file_size": first_payload.get("file_size", 0),
            "file_type": first_payload.get("file_type"),
            "total_chunks": max(
                first_payload.get("total_chunks", 0),
                len(payloads_list),
            ),
            "total_pages": max(
                first_payload.get("total_pages", 0),
                len(pages),
            ),
            "chunking_strategy": first_payload.get("chunking_strategy", "token"),
            "status": first_payload.get("status", "completed"),
            "created_at": first_payload.get("created_at"),
            "processed_at": first_payload.get("processed_at"),
            "metadata": first_payload.get("document_metadata") or {},
        }

    def _scroll_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10000,
    ) -> List[Any]:
        """Scroll through points for document APIs."""
        scroll_filter = self._build_filter(filters)
        offset = None
        records: List[Any] = []
        remaining = limit

        while remaining > 0:
            batch_size = min(remaining, 256)
            batch, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            records.extend(batch)
            remaining -= len(batch)
            if not batch or offset is None:
                break

        return records

    def _normalize_terms(self, text: str) -> List[str]:
        """Lowercase and split into non-trivial terms."""
        return [
            token
            for token in "".join(
                char.lower() if char.isalnum() else " "
                for char in text
            ).split()
            if len(token) > 1
        ]

    def _keyword_score(self, query_terms: List[str], text_terms: List[str]) -> float:
        """Compute a simple overlap score for hybrid re-ranking."""
        if not query_terms or not text_terms:
            return 0.0

        query_set = set(query_terms)
        text_set = set(text_terms)
        overlap = len(query_set & text_set)
        return overlap / max(len(query_set), 1)
