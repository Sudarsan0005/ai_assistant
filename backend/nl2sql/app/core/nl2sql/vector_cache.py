"""
app/core/nl2sql/vector_cache.py
────────────────────────────────────────────────────────────────────────────
Semantic SQL cache backed by pgvector.

How it works:
  1. On every successful NL→SQL execution, store (question, sql, embedding).
  2. On the next query, embed the question and find the nearest stored pair.
  3. If cosine similarity > threshold (default 0.92), reuse the cached SQL
     directly — no LLM call needed.
  4. If 0.75 < similarity <= 0.92, pass the similar queries to the LLM
     for adaptation (vector_adapt mode).
  5. Below 0.75 — proceed to full LLM generation.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from pgvector.psycopg2 import register_vector
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.tables import QueryCache
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class CacheResult:
    sql_query: str
    similarity: float
    natural_language: str
    cache_id: str


class VectorCache:
    """
    Manages the query_cache table for semantic SQL lookup.

    All heavy lifting is done in plain SQL with the pgvector <=> operator
    (cosine distance) for maximum performance.
    """

    HARD_REUSE_THRESHOLD = settings.vector_similarity_threshold   # reuse SQL directly
    SOFT_ADAPT_THRESHOLD = 0.75                                    # adapt with LLM

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    #  Lookup
    # ─────────────────────────────────────────────────────────────────────────

    def find_similar(
        self,
        embedding: List[float],
        top_k: int = 5,
    ) -> List[CacheResult]:
        """
        Return top-k cached queries sorted by cosine similarity (highest first).
        Filters to only return results with similarity > SOFT_ADAPT_THRESHOLD.
        """
        try:
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

            rows = self.db.execute(
                text("""
                    SELECT
                        id,
                        natural_language,
                        sql_query,
                        1 - (embedding <=> :embedding::vector) AS similarity
                    FROM query_cache
                    WHERE 1 - (embedding <=> :embedding::vector) > :threshold
                    ORDER BY similarity DESC
                    LIMIT :top_k
                """),
                {
                    "embedding": embedding_str,
                    "threshold": self.SOFT_ADAPT_THRESHOLD,
                    "top_k": top_k,
                },
            ).fetchall()

            return [
                CacheResult(
                    sql_query=row.sql_query,
                    similarity=float(row.similarity),
                    natural_language=row.natural_language,
                    cache_id=str(row.id),
                )
                for row in rows
            ]

        except Exception as exc:
            logger.warning("Vector cache lookup failed: %s", exc)
            self.db.rollback()
            return []

    def get_exact_match(self, embedding: List[float]) -> Optional[str]:
        """
        Return cached SQL if the best match exceeds HARD_REUSE_THRESHOLD.
        Also increments the usage counter on a hit.
        """
        results = self.find_similar(embedding, top_k=1)
        if not results:
            return None

        best = results[0]
        if best.similarity >= self.HARD_REUSE_THRESHOLD:
            try:
                self.db.execute(
                    text("UPDATE query_cache SET usage_count = usage_count + 1, last_used_at = NOW() WHERE id = :id"),
                    {"id": best.cache_id},
                )
                self.db.commit()
            except Exception as exc:
                logger.warning("Vector cache usage counter update failed: %s", exc)
                self.db.rollback()
            logger.info("Vector cache HIT — similarity=%.4f, sql=%.80s", best.similarity, best.sql_query)
            return best.sql_query

        return None

    def get_adapt_candidates(self, embedding: List[float]) -> List[CacheResult]:
        """
        Return candidates in the soft adapt zone (0.75 < sim <= 0.92).
        These are passed to the LLM for adaptation rather than direct reuse.
        """
        results = self.find_similar(embedding, top_k=3)
        return [r for r in results if r.similarity < self.HARD_REUSE_THRESHOLD]

    # ─────────────────────────────────────────────────────────────────────────
    #  Store
    # ─────────────────────────────────────────────────────────────────────────

    def store(
        self,
        natural_language: str,
        sql_query: str,
        embedding: List[float],
    ) -> None:
        """
        Persist a successful NL→SQL pair. Deduplicates by exact SQL text.
        """
        try:
            existing = self.db.query(QueryCache).filter_by(sql_query=sql_query).first()
            if existing:
                existing.usage_count += 1
                self.db.commit()
                return

            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
            self.db.execute(
                text("""
                    INSERT INTO query_cache (id, natural_language, sql_query, embedding)
                    VALUES (gen_random_uuid(), :nl, :sql, :emb::vector)
                """),
                {"nl": natural_language, "sql": sql_query, "emb": embedding_str},
            )
            self.db.commit()
            logger.info("Vector cache STORED — question=%.80s", natural_language)

        except Exception as exc:
            logger.warning("Vector cache store failed: %s", exc)
            self.db.rollback()
