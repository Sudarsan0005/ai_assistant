"""
Embedding Service
Handles text encoding to vectors using sentence transformers
"""
from typing import List, Tuple
import logging
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Text embedding service using sentence transformers"""
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-base-en-v1.5",
        batch_size: int = 32,
        device: str = "cpu"
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device
        
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name, device=device)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Embedding dimension: {self.dimension}")
    
    def encode_texts(
        self,
        texts: List[str],
        show_progress: bool = False
    ) -> np.ndarray:
        """Encode texts to vectors"""
        if not texts:
            return np.array([])
        
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        return embeddings
    
    def encode_query(self, query: str) -> np.ndarray:
        """Encode a single query"""
        return self.model.encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
    
    def encode_chunks(self, chunks: List[str]) -> Tuple[np.ndarray, List[str]]:
        """Encode chunks and return embeddings with chunk texts"""
        embeddings = self.encode_texts(chunks)
        return embeddings, chunks
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.dimension
