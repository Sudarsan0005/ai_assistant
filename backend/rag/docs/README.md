# Advanced RAG System with Milvus-Only Storage

A production-ready Retrieval-Augmented Generation (RAG) system with vision-based document processing, accurate citation tracking, and **Milvus as the single source of truth** for all storage.

## 🌟 Key Innovation: Milvus-Only Architecture

**No separate MySQL/PostgreSQL needed!** This RAG system uses Milvus for both vector storage AND all metadata, providing:

✅ **Simpler Architecture** - One database instead of two  
✅ **Better Performance** - Single query instead of two databases  
✅ **Atomic Operations** - Vector and metadata always in sync  
✅ **Easier Deployment** - Just start Milvus and go  
✅ **No Sync Issues** - Single source of truth  

See [MILVUS_ARCHITECTURE.md](MILVUS_ARCHITECTURE.md) for detailed explanation.

## 🌟 Features

### Core Capabilities
- **Multi-format Document Processing**: PDF, DOCX, TXT, MD, Images (PNG, JPG, JPEG)
- **Vision-Based Processing**: OCR and layout analysis using PaddleOCR
- **Advanced Chunking**: Token-based, semantic, and hierarchical chunking strategies
- **Milvus Vector Database**: Scalable vector storage and retrieval
- **Hybrid Search**: Combines vector similarity and keyword matching
- **Accurate Citations**: Automatic citation insertion with source tracking
- **Reference Management**: Page-level references with high accuracy
- **Multi-LLM Support**: OpenAI, Anthropic, and more via LiteLLM

### Technical Highlights
- **Embedding Models**: BGE, Sentence Transformers, custom models
- **Citation Tracking**: Sentence-level citation with similarity scoring
- **Document Metadata**: Page numbers, positions, document types
- **Batch Processing**: Efficient embedding generation
- **RESTful API**: FastAPI with async support
- **Production Ready**: Logging, error handling, configuration management

## 📋 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG Pipeline Flow                         │
└─────────────────────────────────────────────────────────────┘

1. Document Ingestion
   ├── Document Parser (with Vision)
   │   ├── PDF parsing with layout analysis
   │   ├── Table extraction
   │   ├── Image extraction and OCR
   │   └── Text structure detection
   │
   ├── Chunking Engine
   │   ├── Token-based chunking
   │   ├── Semantic chunking
   │   └── Hierarchical chunking
   │
   └── Embedding Generation
       └── Vector encoding with Sentence Transformers

2. Vector Storage (Milvus)
   ├── Vector indexing (IVF_FLAT, HNSW)
   ├── Metadata storage
   └── Fast similarity search

3. Query Processing
   ├── Query embedding
   ├── Hybrid retrieval (Vector + Keyword)
   ├── Result ranking
   └── Citation tracking

4. Answer Generation
   ├── Context formatting
   ├── LLM prompt engineering
   ├── Citation insertion
   └── Reference formatting
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Docker and Docker Compose
- 8GB RAM minimum (16GB recommended)
- CUDA-capable GPU (optional, for faster processing)

### Installation

1. **Clone or extract the application**
```bash
cd rag_app
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env and add your API keys
```

4. **Start Milvus**
```bash
docker-compose up -d
```

Wait for Milvus to be healthy:
```bash
docker-compose ps
```

5. **Initialize Milvus Collections**
```bash
python init_milvus.py
```

This creates the required collections for storing document chunks and metadata.

6. **Run the application**
```bash
python main.py
```

The API will be available at `http://localhost:8000`

### Quick Test

```python
from rag_pipeline import RAGPipeline

# Initialize
pipeline = RAGPipeline()

# Ingest document
doc = pipeline.ingest_document(
    file_path="./my_document.pdf",
    filename="my_document.pdf"
)

# Query
response = pipeline.query(
    question="What are the main points?",
    use_citations=True
)

print(response.answer_with_citations)
print(response.references)
```

## 📖 Usage Examples

### 1. Basic Document Ingestion and Query

```python
from rag_pipeline import RAGPipeline

# Initialize pipeline
pipeline = RAGPipeline(
    milvus_host="localhost",
    milvus_port=19530,
    embedding_model="BAAI/bge-base-en-v1.5",
    llm_provider="openai",
    llm_model="gpt-4"
)

# Ingest a document
doc_metadata = pipeline.ingest_document(
    file_path="./research_paper.pdf",
    filename="research_paper.pdf",
    chunking_strategy="token"
)

print(f"Document ingested: {doc_metadata.doc_id}")
print(f"Total chunks: {doc_metadata.total_chunks}")

# Query with citations
response = pipeline.query(
    question="What is the main methodology used?",
    use_citations=True
)

print("Answer:", response.answer_with_citations)
print("\nReferences:")
print(response.references)
```

### 2. Vision-Based Document Processing

```python
# Enable vision processing
pipeline = RAGPipeline(enable_vision=True)

# Process image or scanned PDF
doc = pipeline.ingest_document(
    file_path="./scanned_document.pdf",
    filename="scanned_doc.pdf"
)

# Query about visual content
response = pipeline.query(
    question="What information is shown in the diagrams?"
)
```

### 3. Multi-Document Queries

```python
# Ingest multiple documents
doc_ids = []
for file in ["report1.pdf", "report2.pdf", "report3.pdf"]:
    doc = pipeline.ingest_document(file, file)
    doc_ids.append(doc.doc_id)

# Query across all documents
response = pipeline.query(
    question="Compare the findings across these reports",
    doc_ids=None  # Query all documents
)

# Query specific documents
response = pipeline.query(
    question="What are the differences?",
    doc_ids=[doc_ids[0], doc_ids[1]]
)
```

### 4. Different Chunking Strategies

```python
# Token-based chunking (default)
doc1 = pipeline.ingest_document(
    "document.pdf", "doc.pdf",
    chunking_strategy="token"
)

# Semantic chunking (groups related content)
doc2 = pipeline.ingest_document(
    "document.pdf", "doc.pdf",
    chunking_strategy="semantic"
)

# Hierarchical chunking (parent-child relationships)
doc3 = pipeline.ingest_document(
    "document.pdf", "doc.pdf",
    chunking_strategy="hierarchical"
)
```

## 🔧 API Endpoints

### Document Management

**Upload Document**
```http
POST /documents/upload
Content-Type: multipart/form-data

file: <document_file>
chunking_strategy: token|semantic|hierarchical
```

**List Documents**
```http
GET /documents
```

**Get Document Info**
```http
GET /documents/{doc_id}
```

**Delete Document**
```http
DELETE /documents/{doc_id}
```

**Get Document Chunks**
```http
GET /documents/{doc_id}/chunks
```

### Query

**Query Documents**
```http
POST /query
Content-Type: application/json

{
  "question": "What are the key findings?",
  "doc_ids": ["doc_id_1", "doc_id_2"],
  "use_citations": true
}
```

### Health Check

```http
GET /
```

## ⚙️ Configuration

### Environment Variables

See `.env.example` for all configuration options:

**Milvus Configuration**
- `MILVUS_HOST`: Milvus server host
- `MILVUS_PORT`: Milvus server port
- `MILVUS_COLLECTION_NAME`: Collection name for chunks

**Embedding Configuration**
- `EMBEDDING_MODEL`: Model for text embedding
- `EMBEDDING_DIMENSION`: Vector dimension
- `EMBEDDING_BATCH_SIZE`: Batch size for encoding

**Chunking Configuration**
- `CHUNK_SIZE`: Maximum chunk size in tokens
- `CHUNK_OVERLAP`: Overlap between chunks

**Retrieval Configuration**
- `TOP_K`: Number of chunks to retrieve
- `SIMILARITY_THRESHOLD`: Minimum similarity score
- `VECTOR_WEIGHT`: Weight for vector similarity
- `KEYWORD_WEIGHT`: Weight for keyword matching

**LLM Configuration**
- `LLM_PROVIDER`: openai|anthropic|litellm
- `LLM_MODEL`: Model name
- `LLM_TEMPERATURE`: Generation temperature
- `LLM_MAX_TOKENS`: Maximum tokens in response

**Citation Configuration**
- `CITATION_THRESHOLD`: Minimum similarity for citations
- `MAX_CITATIONS_PER_SENTENCE`: Maximum citations per sentence

## 🧪 Testing

Run the example usage script:

```bash
python example_usage.py
```

This demonstrates:
- Basic document ingestion and query
- Multi-document queries
- Chunking strategy comparison
- Vision-based processing
- Citation management
- Document management

## 🏗️ Project Structure

```
rag_app/
├── main.py                  # FastAPI application
├── rag_pipeline.py          # Main RAG pipeline
├── document_parser.py       # Document parsing with vision
├── chunking.py              # Chunking strategies
├── vector_store.py          # Milvus integration
├── embedding_service.py     # Text embedding
├── retrieval_service.py     # Retrieval and citation
├── llm_service.py           # LLM integration
├── config.py                # Configuration
├── requirements.txt         # Dependencies
├── docker-compose.yml       # Milvus setup
├── .env.example             # Environment template
├── example_usage.py         # Usage examples
└── README.md                # Documentation
```

## 🔍 How Citation Management Works

The RAG system implements accurate citation tracking:

1. **Chunk Indexing**: Each chunk gets a unique citation ID during retrieval
2. **Similarity Scoring**: Sentences are matched to chunks using word overlap
3. **Citation Insertion**: Citations [0], [1], etc. are inserted after relevant sentences
4. **Reference Generation**: Full references with page numbers are compiled
5. **Position Tracking**: Original document positions are preserved

Example output:
```
The study found significant improvements in accuracy [0,1]. 
The methodology involved three phases [2]. Results were 
validated across multiple datasets [1,3].

References:
[0,1] Research Paper.pdf (Pages: 3, 5)
[2] Research Paper.pdf (Page: 7)
[3] Research Paper.pdf (Page: 12)
```

## 🎯 Performance Tips

1. **Batch Processing**: Increase `EMBEDDING_BATCH_SIZE` for faster embedding
2. **GPU Acceleration**: Use CUDA for embedding generation
3. **Chunk Size**: Optimize `CHUNK_SIZE` based on your content
4. **Index Type**: Use HNSW index for large datasets
5. **Hybrid Search**: Adjust weights for your use case

## 🐛 Troubleshooting

**Milvus connection failed**
```bash
# Check Milvus status
docker-compose ps

# Restart Milvus
docker-compose down
docker-compose up -d
```

**Out of memory**
- Reduce `EMBEDDING_BATCH_SIZE`
- Reduce `TOP_K`
- Use smaller embedding model

**OCR not working**
- Install PaddleOCR dependencies
- Check `ENABLE_VISION` setting
- Verify image format support

**Citations not appearing**
- Check `CITATION_THRESHOLD` (lower for more citations)
- Verify context chunks are relevant
- Adjust `MAX_CITATIONS_PER_SENTENCE`

## 📚 Advanced Features

### Custom Embedding Models

```python
pipeline = RAGPipeline(
    embedding_model="sentence-transformers/all-MiniLM-L6-v2"
)
```

### Custom System Prompts

```python
from llm_service import PromptTemplates

custom_prompt = """You are an expert analyst..."""

response = pipeline.query(
    question="Analyze this data",
    custom_system_prompt=custom_prompt
)
```

### Hierarchical Chunking

```python
# Creates parent-child chunk relationships
doc = pipeline.ingest_document(
    "large_document.pdf",
    "doc.pdf",
    chunking_strategy="hierarchical"
)
```

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional document formats
- More embedding models
- Advanced reranking
- Query expansion
- Multi-modal retrieval

## 📄 License

Apache License 2.0

## 🙏 Acknowledgments

Based on RAGFlow's architecture with enhancements:
- Milvus vector database integration
- Accurate citation tracking system
- Vision-based document processing
- Production-ready API design
- Comprehensive error handling

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review example usage
3. Check configuration settings
4. Enable DEBUG mode for detailed logs

---

**Built with ❤️ for production RAG applications**
