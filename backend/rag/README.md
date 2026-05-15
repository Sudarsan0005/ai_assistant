# Advanced RAG System - Structured Edition

> **Production-ready RAG application with clean, maintainable project structure**

## 🎯 What's New

This is the **professionally structured version** of the RAG application with:
- ✅ **Organized folder structure** (no more messy flat layout!)
- ✅ **Milvus-only storage** (no separate database needed)
- ✅ **Modular architecture** (easy to maintain and extend)
- ✅ **Industry-standard layout** (app/, services/, core/, api/)

## 📁 Project Structure

```
rag_app_structured/
├── app/          # Application & configuration
├── services/     # Business logic services
├── core/         # RAG pipeline orchestration
├── api/          # HTTP API layer
├── utils/        # Shared utilities
├── scripts/      # Standalone tools
├── tests/        # Test suite
└── docs/         # Documentation
```

**See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for detailed explanation**

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 3. Start Milvus
```bash
docker-compose up -d
```

### 4. Initialize Database
```bash
python run.py --init
```

### 5. Run Application
```bash
python run.py
```

Visit: http://localhost:8000/docs

## 📖 Documentation

- **[QUICKSTART.md](docs/QUICKSTART.md)** - 5-minute setup guide
- **[README.md](docs/README.md)** - Complete documentation
- **[MILVUS_ARCHITECTURE.md](docs/MILVUS_ARCHITECTURE.md)** - Technical details
- **[PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)** - Structure explanation

## 💡 Key Features

### Milvus-Only Architecture
- **No MySQL/PostgreSQL needed**
- Everything stored in Milvus
- Simple, fast, consistent

### Vision-Based Processing
- OCR with PaddleOCR
- Table extraction
- Layout analysis

### Accurate Citations
- Sentence-level citations
- Page number tracking
- Reference links

### Multiple Chunking Strategies
- Token-based
- Semantic
- Hierarchical

### Multi-LLM Support
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Any provider via LiteLLM

## 🔧 Usage

### Start API Server
```bash
python run.py
```

### Initialize Milvus Collections
```bash
python run.py --init
```

### Run Tests
```bash
python run.py --test
```

### Run Examples
```bash
python -m scripts.example_usage
```

## 📦 Module Organization

### `app/` - Application Layer
- Configuration management
- FastAPI application setup
- Lifecycle management

### `services/` - Business Logic
- Document parsing
- Chunking strategies
- Embedding generation
- Vector storage (Milvus)
- Retrieval and citations
- LLM integration

### `core/` - Orchestration
- RAG pipeline
- Workflow coordination
- Service integration

### `api/` - HTTP Interface
- Request/response models
- Route handlers
- Input validation

### `scripts/` - Tools
- Database initialization
- Usage examples
- Admin scripts

## 🎓 Example Usage

```python
from core.rag_pipeline import RAGPipeline

# Initialize
pipeline = RAGPipeline()

# Ingest document
doc = pipeline.ingest_document(
    file_path="document.pdf",
    filename="document.pdf"
)

# Query with citations
response = pipeline.query(
    question="What are the main findings?",
    use_citations=True
)

print(response.answer_with_citations)
print(response.references)
```

## 🏗️ Architecture Highlights

### Clean Separation
```
API Layer (routes.py)
    ↓
Core Logic (rag_pipeline.py)
    ↓
Services (document_parser, chunking, etc.)
    ↓
Configuration (config.py)
```

### Import Strategy
```python
# From API
from core.rag_pipeline import RAGPipeline
from api.models import QueryRequest

# From core
from services.vector_store import MilvusVectorStore
from services.chunking import get_chunker

# From scripts
from core.rag_pipeline import RAGPipeline
```

## 🆚 Why This Structure?

### Before (Flat)
- ❌ 25+ files in one directory
- ❌ Hard to navigate
- ❌ Unclear relationships
- ❌ Difficult to maintain

### After (Structured)
- ✅ Organized by function
- ✅ Easy to navigate
- ✅ Clear dependencies
- ✅ Easy to maintain
- ✅ Production-ready

## 📊 What's Stored Where?

### Milvus Collections
1. **`document_chunks`** - Vectors + chunk metadata
2. **`document_chunks_documents`** - Document metadata

### File System
- `uploads/` - Uploaded files (temporary)
- `logs/` - Application logs (if enabled)

## 🔍 API Endpoints

- `GET /` - Health check
- `POST /documents/upload` - Upload document
- `POST /query` - Ask questions
- `GET /documents` - List documents
- `GET /documents/{id}` - Get document info
- `DELETE /documents/{id}` - Delete document
- `GET /documents/{id}/chunks` - Get chunks
- `GET /documents/{id}/stats` - Get statistics

Full API docs: http://localhost:8000/docs

## 🛠️ Development

### Adding a New Service
1. Create in `services/` directory
2. Export in `services/__init__.py`
3. Use in `core/rag_pipeline.py`

### Adding a New Endpoint
1. Define model in `api/models.py`
2. Add route in `api/routes.py`
3. Register in `app/main.py`

### Running Tests
```bash
python run.py --test
# or
pytest tests/ -v
```

## 📈 Production Deployment

### Using Docker
```bash
# Build
docker build -t rag-app .

# Run
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e MILVUS_HOST=your_milvus_host \
  rag-app
```

### Using Docker Compose
```bash
docker-compose up -d
```

## 🤝 Contributing

This structure supports:
- Team collaboration
- Parallel development
- Easy testing
- Clean git history

## 📞 Support

- **Documentation**: See `docs/` directory
- **Examples**: See `scripts/example_usage.py`
- **Tests**: See `tests/test_basic.py`
- **Structure**: See `docs/PROJECT_STRUCTURE.md`

## ✨ Summary

**Professional, maintainable, production-ready RAG application with:**
- Clean folder structure
- Milvus-only storage
- Vision-based document processing
- Accurate citation management
- Multi-LLM support
- Complete API
- Comprehensive documentation

**No more messy flat structure! 🎉**

---

**Built with care for production use** 🚀
