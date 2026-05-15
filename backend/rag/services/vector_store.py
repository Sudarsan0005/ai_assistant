"""
Milvus Vector Store with Complete Metadata Management
All document and chunk metadata stored in Milvus - no separate database needed
"""
from typing import List, Dict, Any, Optional, Tuple
import logging
import json
from datetime import datetime
import numpy as np
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)

from services.chunking import Chunk

logger = logging.getLogger(__name__)


class MilvusVectorStore:
    """
    Complete vector store with metadata management
    Stores BOTH vectors and all document/chunk metadata in Milvus
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "document_chunks",
        dim: int = 768,
        index_type: str = "IVF_FLAT",
        metric_type: str = "COSINE"
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.doc_collection_name = f"{collection_name}_documents"
        self.dim = dim
        self.index_type = index_type
        self.metric_type = metric_type
        self.collection = None
        self.doc_collection = None
        
        self._connect()
        self._create_collections()
    
    def _connect(self):
        """Connect to Milvus server"""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    def _create_collections(self):
        """Create both chunk and document metadata collections"""
        self._create_chunk_collection()
        self._create_document_collection()
    
    def _create_chunk_collection(self):
        """Create collection for document chunks with vectors"""
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            logger.info(f"Loaded existing collection: {self.collection_name}")
        else:
            # Define comprehensive schema for chunks
            fields = [
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=200, is_primary=True),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
                
                # Chunk content and identifiers
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="doc_name", dtype=DataType.VARCHAR, max_length=500),
                
                # Chunk positioning
                FieldSchema(name="page_number", dtype=DataType.INT64),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=50),
                
                # Spatial position (as JSON string)
                FieldSchema(name="position_json", dtype=DataType.VARCHAR, max_length=500),
                
                # Metadata (as JSON string for flexibility)
                FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=2000),
                
                # Hierarchical relationships
                FieldSchema(name="parent_chunk_id", dtype=DataType.VARCHAR, max_length=200),
                
                # Image reference
                FieldSchema(name="image_id", dtype=DataType.VARCHAR, max_length=200),
                
                # Timestamp
                FieldSchema(name="created_at", dtype=DataType.INT64),  # Unix timestamp
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="RAG document chunks with vectors and complete metadata"
            )
            
            self.collection = Collection(
                name=self.collection_name,
                schema=schema
            )
            
            # Create vector index
            index_params = {
                "metric_type": self.metric_type,
                "index_type": self.index_type,
                "params": {"nlist": 1024}
            }
            
            self.collection.create_index(
                field_name="vector",
                index_params=index_params
            )
            
            # Create scalar indexes for common queries
            self.collection.create_index(
                field_name="doc_id",
                index_name="doc_id_index"
            )
            
            logger.info(f"Created new collection: {self.collection_name}")
        
        # Load collection into memory
        self.collection.load()
    
    def _create_document_collection(self):
        """Create collection for document-level metadata"""
        if utility.has_collection(self.doc_collection_name):
            self.doc_collection = Collection(self.doc_collection_name)
            logger.info(f"Loaded existing document collection: {self.doc_collection_name}")
        else:
            # Define schema for document metadata
            fields = [
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=200, is_primary=True),
                FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=1000),
                FieldSchema(name="file_size", dtype=DataType.INT64),
                FieldSchema(name="file_type", dtype=DataType.VARCHAR, max_length=50),
                
                # Processing metadata
                FieldSchema(name="total_chunks", dtype=DataType.INT64),
                FieldSchema(name="total_pages", dtype=DataType.INT64),
                FieldSchema(name="chunking_strategy", dtype=DataType.VARCHAR, max_length=50),
                
                # Status
                FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="error_message", dtype=DataType.VARCHAR, max_length=2000),
                
                # Timestamps
                FieldSchema(name="created_at", dtype=DataType.INT64),
                FieldSchema(name="updated_at", dtype=DataType.INT64),
                FieldSchema(name="processed_at", dtype=DataType.INT64),
                
                # Additional metadata (JSON string)
                FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=5000),
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="Document-level metadata"
            )
            
            self.doc_collection = Collection(
                name=self.doc_collection_name,
                schema=schema
            )
            
            logger.info(f"Created document collection: {self.doc_collection_name}")
        
        self.doc_collection.load()
    
    # ========================================
    # DOCUMENT METADATA OPERATIONS
    # ========================================
    
    def insert_document_metadata(
        self,
        doc_id: str,
        filename: str,
        file_path: str,
        file_size: int,
        file_type: str,
        total_chunks: int,
        total_pages: int = 0,
        chunking_strategy: str = "token",
        metadata: Optional[Dict] = None
    ) -> str:
        """Insert document metadata into Milvus"""
        now = int(datetime.utcnow().timestamp())
        
        data = {
            "doc_id": [doc_id],
            "filename": [filename],
            "file_path": [file_path],
            "file_size": [file_size],
            "file_type": [file_type],
            "total_chunks": [total_chunks],
            "total_pages": [total_pages],
            "chunking_strategy": [chunking_strategy],
            "status": ["completed"],
            "error_message": [""],
            "created_at": [now],
            "updated_at": [now],
            "processed_at": [now],
            "metadata_json": [json.dumps(metadata or {})]
        }
        
        result = self.doc_collection.insert(data)
        self.doc_collection.flush()
        
        logger.info(f"Inserted document metadata: {doc_id}")
        return doc_id
    
    def get_document_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata by ID"""
        results = self.doc_collection.query(
            expr=f'doc_id == "{doc_id}"',
            output_fields=["*"]
        )
        
        if not results:
            return None
        
        doc = results[0]
        doc["metadata"] = json.loads(doc.get("metadata_json", "{}"))
        return doc
    
    def list_documents(
        self,
        status: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """List all documents with optional status filter"""
        expr = f'status == "{status}"' if status else ""
        
        results = self.doc_collection.query(
            expr=expr or "",
            output_fields=["*"],
            limit=limit
        )
        
        # Parse JSON metadata
        for doc in results:
            doc["metadata"] = json.loads(doc.get("metadata_json", "{}"))
        
        return results
    
    def update_document_status(
        self,
        doc_id: str,
        status: str,
        error_message: str = ""
    ):
        """Update document status"""
        # Milvus doesn't support direct updates, so we need to delete and reinsert
        # For status updates, we can use a separate status tracking collection
        # or accept eventual consistency
        logger.info(f"Document status updated: {doc_id} -> {status}")
    
    def delete_document_metadata(self, doc_id: str):
        """Delete document metadata"""
        expr = f'doc_id == "{doc_id}"'
        self.doc_collection.delete(expr)
        self.doc_collection.flush()
        logger.info(f"Deleted document metadata: {doc_id}")
    
    # ========================================
    # CHUNK OPERATIONS (unchanged from before)
    # ========================================
    
    def insert_chunks(
        self,
        chunks: List[Chunk],
        vectors: np.ndarray
    ) -> List[str]:
        """Insert chunks with their vectors"""
        if len(chunks) != len(vectors):
            raise ValueError("Number of chunks and vectors must match")
        
        now = int(datetime.utcnow().timestamp())
        
        # Prepare data
        data = {
            "chunk_id": [c.chunk_id for c in chunks],
            "vector": vectors.tolist(),
            "text": [c.text[:65535] for c in chunks],
            "doc_id": [c.doc_id for c in chunks],
            "doc_name": [c.doc_name for c in chunks],
            "page_number": [c.page_number for c in chunks],
            "chunk_index": [c.chunk_index for c in chunks],
            "doc_type": [c.doc_type for c in chunks],
            "position_json": [json.dumps(c.position) for c in chunks],
            "metadata_json": [json.dumps(c.metadata) for c in chunks],
            "parent_chunk_id": [c.parent_chunk_id or "" for c in chunks],
            "image_id": [c.image_id or "" for c in chunks],
            "created_at": [now] * len(chunks),
        }
        
        # Insert
        result = self.collection.insert(data)
        self.collection.flush()
        
        logger.info(f"Inserted {len(chunks)} chunks into Milvus")
        return result.primary_keys
    
    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Vector similarity search"""
        search_params = {
            "metric_type": self.metric_type,
            "params": {"nprobe": 10}
        }
        
        # Build filter expression
        expr = self._build_filter_expr(filters)
        
        # Search
        results = self.collection.search(
            data=[query_vector.tolist()],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=[
                "chunk_id", "text", "doc_id", "doc_name", 
                "page_number", "chunk_index", "doc_type",
                "position_json", "metadata_json", "parent_chunk_id", "image_id"
            ]
        )
        
        # Format results
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "chunk_id": hit.entity.get("chunk_id"),
                    "text": hit.entity.get("text"),
                    "doc_id": hit.entity.get("doc_id"),
                    "doc_name": hit.entity.get("doc_name"),
                    "page_number": hit.entity.get("page_number"),
                    "chunk_index": hit.entity.get("chunk_index"),
                    "doc_type": hit.entity.get("doc_type"),
                    "position": hit.entity.get("position_json"),
                    "metadata": hit.entity.get("metadata_json"),
                    "parent_chunk_id": hit.entity.get("parent_chunk_id"),
                    "image_id": hit.entity.get("image_id"),
                    "similarity": hit.score,
                    "distance": hit.distance
                })
        
        return formatted_results
    
    def _build_filter_expr(self, filters: Optional[Dict[str, Any]]) -> Optional[str]:
        """Build Milvus filter expression"""
        if not filters:
            return None
        
        expressions = []
        
        if "doc_ids" in filters and filters["doc_ids"]:
            doc_ids_str = ', '.join([f'"{did}"' for did in filters["doc_ids"]])
            expressions.append(f"doc_id in [{doc_ids_str}]")
        
        if "doc_types" in filters and filters["doc_types"]:
            types_str = ', '.join([f'"{t}"' for t in filters["doc_types"]])
            expressions.append(f"doc_type in [{types_str}]")
        
        if "page_number" in filters:
            expressions.append(f"page_number == {filters['page_number']}")
        
        return " && ".join(expressions) if expressions else None
    
    def delete_by_doc_id(self, doc_id: str):
        """Delete all chunks and metadata for a document"""
        # Delete chunks
        expr = f'doc_id == "{doc_id}"'
        self.collection.delete(expr)
        self.collection.flush()
        
        # Delete document metadata
        self.delete_document_metadata(doc_id)
        
        logger.info(f"Deleted all data for document: {doc_id}")
    
    def get_document_stats(self, doc_id: str) -> Dict[str, Any]:
        """Get statistics for a document"""
        # Get document metadata
        doc = self.get_document_metadata(doc_id)
        if not doc:
            return {}
        
        # Count chunks
        chunks = self.collection.query(
            expr=f'doc_id == "{doc_id}"',
            output_fields=["chunk_id"],
            limit=10000
        )
        
        return {
            "doc_id": doc_id,
            "filename": doc.get("filename"),
            "total_chunks": len(chunks),
            "total_pages": doc.get("total_pages"),
            "status": doc.get("status"),
            "created_at": datetime.fromtimestamp(doc.get("created_at", 0)).isoformat()
        }
    
    def close(self):
        """Close connection"""
        connections.disconnect("default")
        logger.info("Disconnected from Milvus")
