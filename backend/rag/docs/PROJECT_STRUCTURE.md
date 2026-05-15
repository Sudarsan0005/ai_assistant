# Project Structure Documentation

## 📁 Folder Organization

```
rag_app_structured/
├── app/                        # Application configuration and entry point
│   ├── __init__.py
│   ├── config.py              # Settings and configuration
│   └── main.py                # FastAPI application
│
├── services/                   # Business logic services
│   ├── __init__.py            # Service exports
│   ├── document_parser.py     # Document parsing with vision
│   ├── chunking.py            # Chunking strategies
│   ├── embedding_service.py   # Text embedding
│   ├── vector_store.py        # Milvus integration
│   ├── retrieval_service.py   # Retrieval and citations
│   └── llm_service.py         # LLM integration
│
├── core/                       # Core business logic
│   ├── __init__.py
│   └── rag_pipeline.py        # Main RAG pipeline orchestration
│
├── api/                        # API layer
│   ├── __init__.py
│   ├── models.py              # Pydantic request/response models
│   └── routes.py              # FastAPI route handlers
│
├── utils/                      # Utility functions and helpers
│   ├── __init__.py
│   └── api_client.py          # API client for testing
│
├── scripts/                    # Standalone scripts
│   ├── init_milvus.py         # Database initialization
│   └── example_usage.py       # Usage examples
│
├── tests/                      # Test suite
│   ├── __init__.py
│   └── test_basic.py          # Basic tests
│
├── docs/                       # Documentation
│   ├── README.md              # Main documentation
│   ├── MILVUS_ARCHITECTURE.md # Architecture details
│   └── QUICKSTART.md          # Quick start guide
│
├── run.py                      # Main runner script
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
├── .gitignore                 # Git ignore rules
├── docker-compose.yml         # Milvus setup
└── Dockerfile                 # Application container
```

## 🎯 Design Principles

### 1. Separation of Concerns
- **app/**: Application-level configuration and startup
- **services/**: Individual service modules (single responsibility)
- **core/**: High-level business logic orchestration
- **api/**: HTTP API layer (routes, models)
- **utils/**: Shared utilities
- **scripts/**: Standalone tools

### 2. Dependency Flow
```
API Layer (api/)
    ↓
Core Logic (core/)
    ↓
Services (services/)
    ↓
Configuration (app/config.py)
```

### 3. Import Strategy
- Use absolute imports: `from services.chunking import Chunk`
- Each module exports via `__init__.py`
- No circular dependencies

## 📦 Module Descriptions

### app/
**Purpose**: Application configuration and FastAPI setup

**Files**:
- `config.py`: Centralized settings using Pydantic
- `main.py`: FastAPI application with lifespan management

**Responsibilities**:
- Load environment variables
- Initialize FastAPI app
- Register middleware and routers
- Manage application lifecycle

### services/
**Purpose**: Independent, reusable service modules

**Files**:
- `document_parser.py`: Parse PDFs, DOCX, images with OCR
- `chunking.py`: Token, semantic, hierarchical chunking
- `embedding_service.py`: Text-to-vector encoding
- `vector_store.py`: Milvus database operations
- `retrieval_service.py`: Hybrid search and citations
- `llm_service.py`: LLM integration (OpenAI, Anthropic)

**Key Principle**: Each service is independent and testable

### core/
**Purpose**: High-level business logic orchestration

**Files**:
- `rag_pipeline.py`: Orchestrates all services for end-to-end RAG

**Responsibilities**:
- Document ingestion workflow
- Query processing workflow
- Coordinate between services
- Handle errors and retries

### api/
**Purpose**: HTTP API interface

**Files**:
- `models.py`: Request/response schemas
- `routes.py`: API endpoints

**Responsibilities**:
- HTTP request validation
- Response serialization
- Error handling
- Route organization

### utils/
**Purpose**: Shared utilities and helpers

**Files**:
- `api_client.py`: Python client for API testing

**Can include**:
- Logging utilities
- Data formatters
- Common helpers

### scripts/
**Purpose**: Standalone tools and examples

**Files**:
- `init_milvus.py`: Initialize Milvus collections
- `example_usage.py`: Usage demonstrations

**Characteristics**:
- Runnable standalone
- Not imported by application
- Development and admin tools

### tests/
**Purpose**: Test suite

**Files**:
- `test_basic.py`: Basic functionality tests

**Structure**:
- Mirror the app structure
- Use pytest conventions

### docs/
**Purpose**: Documentation

**Files**:
- `README.md`: Complete guide
- `MILVUS_ARCHITECTURE.md`: Technical details
- `QUICKSTART.md`: Quick start

## 🚀 Running the Application

### Method 1: Using run.py (Recommended)
```bash
# Start API server
python run.py

# Initialize Milvus
python run.py --init

# Run tests
python run.py --test
```

### Method 2: Direct Module Execution
```bash
# Start server
python -m app.main

# Initialize Milvus
python -m scripts.init_milvus

# Run examples
python -m scripts.example_usage
```

### Method 3: Using uvicorn
```bash
uvicorn app.main:app --reload
```

## 📝 Import Examples

### From API Layer
```python
# In api/routes.py
from app.config import settings
from core.rag_pipeline import RAGPipeline
from api.models import QueryRequest, QueryResponse
```

### From Core Layer
```python
# In core/rag_pipeline.py
from services.document_parser import DocumentParser
from services.chunking import get_chunker
from services.vector_store import MilvusVectorStore
from app.config import settings
```

### From Scripts
```python
# In scripts/example_usage.py
from core.rag_pipeline import RAGPipeline
from app.config import settings
```

### From Tests
```python
# In tests/test_basic.py
from services.chunking import get_chunker
from services.document_parser import DocumentParser
```

## 🔧 Adding New Features

### Adding a New Service
1. Create file in `services/` directory
2. Implement service class
3. Export in `services/__init__.py`
4. Use in `core/rag_pipeline.py`

**Example**:
```python
# services/reranker_service.py
class RerankerService:
    def rerank(self, query, chunks):
        # Implementation
        pass

# services/__init__.py
from services.reranker_service import RerankerService
__all__ = [..., "RerankerService"]

# core/rag_pipeline.py
from services.reranker_service import RerankerService
```

### Adding a New API Endpoint
1. Define models in `api/models.py`
2. Add route in `api/routes.py`
3. Register router in `app/main.py`

**Example**:
```python
# api/models.py
class SummaryRequest(BaseModel):
    doc_id: str

# api/routes.py
summary_router = APIRouter(prefix="/summary", tags=["Summary"])

@summary_router.post("")
async def summarize(request: SummaryRequest):
    # Implementation
    pass

# app/main.py
from api.routes import summary_router
app.include_router(summary_router)
```

## 📊 Benefits of This Structure

### ✅ Maintainability
- Clear module boundaries
- Easy to find code
- Logical organization

### ✅ Scalability
- Easy to add new services
- Independent module growth
- Parallel development

### ✅ Testability
- Services are isolated
- Easy to mock dependencies
- Clear test structure

### ✅ Readability
- Self-documenting structure
- Consistent naming
- Clear dependencies

### ✅ Professional
- Industry-standard layout
- Production-ready
- Team-friendly

## 🔍 Comparison: Flat vs Structured

### Flat Structure (OLD) ❌
```
rag_app/
├── config.py
├── document_parser.py
├── chunking.py
├── embedding_service.py
├── vector_store.py
├── retrieval_service.py
├── llm_service.py
├── rag_pipeline.py
├── main.py
├── init_milvus.py
├── example_usage.py
├── test_basic.py
├── api_client.py
└── ... (25 files in one folder)
```

**Problems**:
- Hard to navigate
- Unclear relationships
- All files at same level
- No logical grouping

### Structured Layout (NEW) ✅
```
rag_app_structured/
├── app/          → Application
├── services/     → Business logic
├── core/         → Orchestration
├── api/          → HTTP interface
├── utils/        → Helpers
├── scripts/      → Tools
├── tests/        → Tests
└── docs/         → Documentation
```

**Benefits**:
- Clear organization
- Easy navigation
- Logical grouping
- Professional structure

## 🎓 Learning the Structure

### For New Developers
1. Start with `docs/README.md`
2. Look at `app/main.py` (entry point)
3. Explore `api/routes.py` (endpoints)
4. Dive into `core/rag_pipeline.py` (main logic)
5. Study `services/` (individual components)

### For Users
1. Read `docs/QUICKSTART.md`
2. Run `python run.py --init`
3. Run `python run.py`
4. Check examples in `scripts/example_usage.py`

## 📈 Next Steps

This structure supports:
- ✅ Microservices architecture
- ✅ Docker containerization
- ✅ CI/CD pipelines
- ✅ Multiple environments
- ✅ Team collaboration

Ready for production! 🚀
