# Milvus-Only Architecture Documentation

## Why Use Only Milvus? 🎯

This RAG application uses **Milvus as the single source of truth** for all data storage, eliminating the need for a separate MySQL/PostgreSQL database.

## Architecture Comparison

### ❌ Traditional Approach (2 Databases)
```
┌─────────────────┐      ┌──────────────────┐
│   PostgreSQL    │      │     Milvus       │
│  (Metadata DB)  │      │  (Vector DB)     │
├─────────────────┤      ├──────────────────┤
│ - doc_id        │      │ - chunk_id       │
│ - filename      │      │ - vector         │
│ - status        │      │ - text           │
│ - created_at    │      │ - doc_id (FK)    │
└─────────────────┘      └──────────────────┘
       ↓                        ↓
    Problems:
    ✗ Two databases to maintain
    ✗ Data synchronization issues
    ✗ Two network calls per operation
    ✗ Potential consistency problems
    ✗ More complex deployment
```

### ✅ Milvus-Only Approach (1 Database)
```
┌────────────────────────────────────┐
│            Milvus                  │
│  (Unified Vector + Metadata DB)    │
├────────────────────────────────────┤
│  Collection: document_chunks       │
│  - chunk_id (PK)                   │
│  - vector (FLOAT_VECTOR)           │
│  - text, doc_id, page_number       │
│  - position, metadata (JSON)       │
│  - created_at, etc.                │
├────────────────────────────────────┤
│  Collection: documents_metadata    │
│  - doc_id (PK)                     │
│  - filename, file_path, file_size  │
│  - total_chunks, status            │
│  - created_at, updated_at          │
│  - metadata (JSON)                 │
└────────────────────────────────────┘
       ↓
    Benefits:
    ✓ Single database to maintain
    ✓ Atomic operations
    ✓ One network call
    ✓ Always consistent
    ✓ Simpler deployment
    ✓ Better performance
```

## Data Storage Model

### 1. Document Metadata Collection

**Collection Name:** `document_chunks_documents`

**Purpose:** Stores document-level metadata

**Schema:**
```python
{
    "doc_id": VARCHAR(200),          # Primary key, UUID
    "filename": VARCHAR(500),         # Original filename
    "file_path": VARCHAR(1000),       # Storage path
    "file_size": INT64,               # Size in bytes
    "file_type": VARCHAR(50),         # pdf, docx, txt, etc.
    
    # Processing metadata
    "total_chunks": INT64,            # Number of chunks created
    "total_pages": INT64,             # Total pages in document
    "chunking_strategy": VARCHAR(50), # token, semantic, hierarchical
    
    # Status tracking
    "status": VARCHAR(50),            # processing, completed, failed
    "error_message": VARCHAR(2000),   # Error details if failed
    
    # Timestamps (Unix timestamp)
    "created_at": INT64,              # When uploaded
    "updated_at": INT64,              # Last modified
    "processed_at": INT64,            # When processing completed
    
    # Flexible metadata
    "metadata_json": VARCHAR(5000)    # Additional metadata as JSON
}
```

### 2. Document Chunks Collection

**Collection Name:** `document_chunks`

**Purpose:** Stores chunks with vectors and metadata

**Schema:**
```python
{
    "chunk_id": VARCHAR(200),         # Primary key
    "vector": FLOAT_VECTOR[768],      # Embedding vector
    
    # Content
    "text": VARCHAR(65535),           # Chunk text (up to 64KB)
    "doc_id": VARCHAR(200),           # Reference to document
    "doc_name": VARCHAR(500),         # Document name
    
    # Position in document
    "page_number": INT64,             # Page number
    "chunk_index": INT64,             # Index within document
    "doc_type": VARCHAR(50),          # text, table, image, title
    
    # Spatial position (for citations)
    "position_json": VARCHAR(500),    # {x0, y0, x1, y1}
    
    # Metadata
    "metadata_json": VARCHAR(2000),   # Additional metadata
    
    # Relationships
    "parent_chunk_id": VARCHAR(200),  # For hierarchical chunking
    "image_id": VARCHAR(200),         # Image reference if applicable
    
    # Timestamp
    "created_at": INT64               # When created
}
```

## Database Operations

### Document Ingestion Flow

```python
# 1. Parse document
sections = parser.parse("document.pdf")

# 2. Chunk sections
chunks = chunker.chunk_sections(sections, doc_id, filename)

# 3. Generate embeddings
embeddings = embedding_service.encode_texts([c.text for c in chunks])

# 4. Store chunks in Milvus (ONE operation)
vector_store.insert_chunks(chunks, embeddings)

# 5. Store document metadata in Milvus (ONE operation)
vector_store.insert_document_metadata(
    doc_id=doc_id,
    filename=filename,
    total_chunks=len(chunks),
    # ... other fields
)

# ✓ Everything in Milvus, no synchronization needed!
```

### Query Flow

```python
# 1. Encode query
query_vector = embedding_service.encode_query("What is this about?")

# 2. Search Milvus (ONE operation - gets chunks + metadata)
results = vector_store.search(
    query_vector=query_vector,
    top_k=10,
    filters={"doc_ids": ["doc123"]}
)

# Results contain everything:
# - Chunk text
# - Page numbers
# - Positions (for citations)
# - Document names
# - All metadata

# 3. Generate answer with citations
# All information needed is already retrieved!
```

### Document Management

```python
# Get document metadata
doc = vector_store.get_document_metadata(doc_id)
# Returns: {doc_id, filename, status, total_chunks, ...}

# List all documents
docs = vector_store.list_documents(status="completed")
# Returns: [{doc1}, {doc2}, ...]

# Delete document (atomic - removes chunks + metadata)
vector_store.delete_by_doc_id(doc_id)
# ✓ Both chunks and metadata deleted in one operation

# Get document stats
stats = vector_store.get_document_stats(doc_id)
# Returns: {doc_id, filename, total_chunks, created_at, ...}
```

## Milvus Collection Features

### Indexes

**Vector Index (for similarity search):**
- Type: IVF_FLAT (can be changed to HNSW for better performance)
- Metric: COSINE similarity
- Parameters: nlist=1024, nprobe=10

**Scalar Indexes (for filtering):**
- `doc_id` index for fast document filtering
- Enables efficient queries like: "Find chunks from doc123"

### Filtering

Milvus supports powerful scalar filtering:

```python
# Filter by document
expr = 'doc_id == "doc123"'

# Filter by multiple documents
expr = 'doc_id in ["doc1", "doc2", "doc3"]'

# Filter by page number
expr = 'page_number >= 5 && page_number <= 10'

# Filter by document type
expr = 'doc_type in ["table", "image"]'

# Complex filters
expr = 'doc_id == "doc123" && page_number >= 5 && doc_type == "text"'
```

### JSON Fields

For flexible metadata storage, we use VARCHAR fields containing JSON:

```python
# Store complex metadata
metadata = {
    "author": "John Doe",
    "department": "Engineering",
    "tags": ["technical", "report"],
    "custom_field": "value"
}

# Stored as JSON string in Milvus
metadata_json = json.dumps(metadata)

# Retrieved and parsed
result = vector_store.get_chunk_by_id(chunk_id)
metadata = json.loads(result["metadata_json"])
```

## Performance Characteristics

### Advantages

1. **Lower Latency**
   - Single database query vs. 2 separate queries
   - Reduced network overhead
   - No cross-database joins needed

2. **Better Consistency**
   - Atomic operations (vector + metadata together)
   - No synchronization delays
   - Single transaction boundary

3. **Simpler Deployment**
   - One database to configure
   - One connection pool to manage
   - Fewer failure points

4. **Easier Scaling**
   - Scale Milvus horizontally
   - No need to sync multiple databases
   - Consistent performance characteristics

### Milvus Scalability

- **Millions of vectors**: Milvus handles 100M+ vectors efficiently
- **Horizontal scaling**: Add more Milvus nodes as needed
- **Fast queries**: Sub-100ms latency for similarity search
- **Rich metadata**: Up to 256 scalar fields per collection

## Migration from Dual-Database Setup

If you already have a PostgreSQL + Milvus setup:

```python
# 1. Export from PostgreSQL
docs = postgres_db.query("SELECT * FROM documents")

# 2. Import to Milvus
for doc in docs:
    vector_store.insert_document_metadata(
        doc_id=doc.id,
        filename=doc.filename,
        # ... other fields
    )

# 3. Verify data
milvus_docs = vector_store.list_documents()
assert len(milvus_docs) == len(docs)

# 4. Decommission PostgreSQL
```

## Database Initialization

Run the initialization script:

```bash
# Initialize Milvus collections
python init_milvus.py

# Show collection stats
python init_milvus.py --stats

# Reset all collections (WARNING: deletes data!)
python init_milvus.py --reset --yes
```

This creates:
- `document_chunks` collection with vector index
- `document_chunks_documents` collection for metadata
- All necessary indexes

## Monitoring and Maintenance

### Check Collection Status

```python
from pymilvus import utility, Collection

# List all collections
collections = utility.list_collections()
print(f"Collections: {collections}")

# Get collection stats
collection = Collection("document_chunks")
print(f"Entities: {collection.num_entities}")
```

### Backup and Restore

Milvus provides backup/restore capabilities:

```bash
# Backup (if using Milvus 2.3+)
# Use Milvus backup tool or volume snapshots

# For Docker volumes
docker run --rm -v milvus_volumes:/backup \
    -v $(pwd):/output \
    alpine tar czf /output/milvus_backup.tar.gz /backup
```

## Best Practices

1. **Use Milvus 2.3+**: Better stability and features
2. **Enable vector index**: Critical for performance
3. **Use scalar indexes**: For frequently filtered fields
4. **Batch operations**: Insert multiple chunks at once
5. **Monitor memory**: Milvus loads collections into memory
6. **Regular backups**: Backup Milvus volumes regularly

## Conclusion

Using Milvus as the single source of truth simplifies architecture while improving performance and reliability. It's the **right choice** for RAG applications where:

- Vector search is the primary operation
- Metadata is tied to vectors
- Simple CRUD operations are sufficient
- Performance and consistency matter

**No MySQL/PostgreSQL needed! 🎉**
