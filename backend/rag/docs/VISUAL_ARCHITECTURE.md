# Visual Architecture Guide 🎨

## 📊 Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG Application Architecture                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          USER / CLIENT                               │
│                    (Web Browser, API Client)                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP Requests
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        API LAYER (api/)                              │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   routes.py  │  │  models.py   │  │ __init__.py  │             │
│  │              │  │              │  │              │             │
│  │ • Health     │  │ • Request    │  │ • Exports    │             │
│  │ • Upload     │  │   schemas    │  │              │             │
│  │ • Query      │  │ • Response   │  │              │             │
│  │ • Delete     │  │   schemas    │  │              │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Calls
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       CORE LAYER (core/)                             │
├─────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                   rag_pipeline.py                              │ │
│  │                                                                │ │
│  │  • ingest_document()  - Orchestrates ingestion workflow       │ │
│  │  • query()            - Orchestrates query workflow           │ │
│  │  • delete_document()  - Manages document deletion             │ │
│  │  • list_documents()   - Lists all documents                   │ │
│  │                                                                │ │
│  └────────────────────────┬──────────────────────────────────────┘ │
└───────────────────────────┼──────────────────────────────────────────┘
                            │ Uses
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SERVICES LAYER (services/)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ document_parser  │  │    chunking      │  │  embedding      │  │
│  │      .py         │  │      .py         │  │   _service.py   │  │
│  │                  │  │                  │  │                 │  │
│  │ • PDF parsing    │  │ • Token-based    │  │ • BGE model     │  │
│  │ • DOCX parsing   │  │ • Semantic       │  │ • Encode text   │  │
│  │ • OCR (vision)   │  │ • Hierarchical   │  │ • Batch encode  │  │
│  │ • Table extract  │  │                  │  │                 │  │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘  │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │  vector_store    │  │   retrieval      │  │   llm_service   │  │
│  │      .py         │  │   _service.py    │  │      .py        │  │
│  │                  │  │                  │  │                 │  │
│  │ • Milvus ops     │  │ • Hybrid search  │  │ • OpenAI        │  │
│  │ • Insert chunks  │  │ • Citations      │  │ • Anthropic     │  │
│  │ • Vector search  │  │ • Reranking      │  │ • Answer gen    │  │
│  │ • Metadata CRUD  │  │                  │  │                 │  │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘  │
│                                                                      │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ Configured by
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  APPLICATION LAYER (app/)                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐           ┌──────────────┐                       │
│  │  config.py   │           │   main.py    │                       │
│  │              │           │              │                       │
│  │ • Settings   │◄──────────┤ • FastAPI    │                       │
│  │ • Env vars   │           │ • Startup    │                       │
│  │ • Defaults   │           │ • Shutdown   │                       │
│  └──────────────┘           └──────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SYSTEMS                                  │
├─────────────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │   Milvus   │  │  OpenAI    │  │ Anthropic  │  │ File System │  │
│  │  (Vector   │  │   (LLM)    │  │   (LLM)    │  │  (Uploads)  │  │
│  │    DB)     │  │            │  │            │  │             │  │
│  └────────────┘  └────────────┘  └────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow Diagrams

### 1. Document Ingestion Flow

```
┌──────────┐
│  User    │
│ uploads  │
│   PDF    │
└────┬─────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│  API Layer (routes.py)                      │
│  POST /documents/upload                     │
└────┬────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│  Core Layer (rag_pipeline.py)               │
│  ingest_document()                          │
└────┬────────────────────────────────────────┘
     │
     ├─────────────────────────────────────────┐
     │                                         │
     ▼                                         ▼
┌──────────────┐                    ┌──────────────────┐
│  Services    │                    │  Services        │
│  document    │  Parse sections    │  chunking        │
│  _parser.py  ├───────────────────►│  .py             │
│              │                    │                  │
│  • PDF OCR   │                    │  • Token chunks  │
│  • Tables    │                    │  • Overlapping   │
│  • Layout    │                    │  • Metadata      │
└──────────────┘                    └────────┬─────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │  Services        │
                                    │  embedding       │
                                    │  _service.py     │
                                    │                  │
                                    │  • Encode text   │
                                    │  • Generate      │
                                    │    vectors       │
                                    └────────┬─────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │  Services        │
                                    │  vector_store    │
                                    │  .py             │
                                    │                  │
                                    │  • Store chunks  │
                                    │  • Store vectors │
                                    │  • Store metadata│
                                    └────────┬─────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │     Milvus       │
                                    │                  │
                                    │  Collections:    │
                                    │  • chunks        │
                                    │  • documents     │
                                    └──────────────────┘
```

---

### 2. Query Flow

```
┌──────────┐
│  User    │
│  asks    │
│ question │
└────┬─────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│  API Layer (routes.py)                      │
│  POST /query                                │
└────┬────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│  Core Layer (rag_pipeline.py)               │
│  query()                                    │
└────┬────────────────────────────────────────┘
     │
     ├───────────────────────────────────────────┐
     │                                           │
     ▼                                           ▼
┌──────────────┐                    ┌──────────────────┐
│  Services    │                    │  Services        │
│  embedding   │  Encode query      │  retrieval       │
│  _service.py ├───────────────────►│  _service.py     │
│              │                    │                  │
│  • Query     │                    │  • Hybrid search │
│    vector    │                    │  • Vector + text │
│              │                    │  • Top-K chunks  │
└──────────────┘                    └────────┬─────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │     Milvus       │
                                    │                  │
                                    │  • Search vectors│
                                    │  • Filter docs   │
                                    │  • Return chunks │
                                    └────────┬─────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │  Services        │
                                    │  llm_service     │
                                    │  .py             │
                                    │                  │
                                    │  • Format prompt │
                                    │  • Generate ans  │
                                    │  • With context  │
                                    └────────┬─────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │  Services        │
                                    │  retrieval       │
                                    │  _service.py     │
                                    │                  │
                                    │  • Insert        │
                                    │    citations     │
                                    │  • Format refs   │
                                    └────────┬─────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │  Return to user  │
                                    │                  │
                                    │  • Answer        │
                                    │  • Citations     │
                                    │  • References    │
                                    └──────────────────┘
```

---

## 📦 Module Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                    Dependency Hierarchy                      │
└─────────────────────────────────────────────────────────────┘

Level 0 (Base):
┌──────────────┐
│ app/config   │  ← Configuration (no dependencies)
└──────────────┘

Level 1 (Services):
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  document_   │  │   chunking   │  │  embedding_  │
│  parser      │  │              │  │  service     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┴─────────────────┘
                         │
                    Depends on
                         │
                    ┌────▼─────┐
                    │  config  │
                    └──────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  vector_     │  │  retrieval_  │  │  llm_        │
│  store       │  │  service     │  │  service     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┴─────────────────┘
                         │
                    Depends on
                         │
            ┌────────────▼────────────┐
            │  Other services + config│
            └─────────────────────────┘

Level 2 (Core):
┌──────────────┐
│  rag_        │
│  pipeline    │
└──────┬───────┘
       │
  Depends on
       │
  ┌────▼─────────┐
  │ All services │
  └──────────────┘

Level 3 (API):
┌──────────────┐  ┌──────────────┐
│  models      │  │  routes      │
└──────────────┘  └──────┬───────┘
                         │
                    Depends on
                         │
                  ┌──────▼───────┐
                  │ rag_pipeline │
                  │  + models    │
                  └──────────────┘

Level 4 (Application):
┌──────────────┐
│  main        │
└──────┬───────┘
       │
  Depends on
       │
  ┌────▼─────┐
  │ routes   │
  │ + config │
  └──────────┘
```

---

## 🎯 Import Map

```
api/routes.py
    ├─► core.rag_pipeline.RAGPipeline
    ├─► api.models.QueryRequest
    ├─► api.models.QueryResponse
    └─► app.config.settings

core/rag_pipeline.py
    ├─► services.document_parser.DocumentParser
    ├─► services.chunking.get_chunker
    ├─► services.embedding_service.EmbeddingService
    ├─► services.vector_store.MilvusVectorStore
    ├─► services.retrieval_service.RetrievalService
    ├─► services.llm_service.LLMService
    └─► app.config.settings

services/retrieval_service.py
    ├─► services.vector_store.MilvusVectorStore
    ├─► services.embedding_service.EmbeddingService
    └─► app.config.settings

services/vector_store.py
    ├─► services.chunking.Chunk
    └─► (No other internal deps)

services/chunking.py
    └─► services.document_parser.ParsedSection

app/main.py
    ├─► api.routes.*
    ├─► core.rag_pipeline.RAGPipeline
    └─► app.config.settings
```

---

## 🗂️ File Organization Principles

### 1. Single Responsibility
```
✅ DO:
services/document_parser.py    # Only document parsing
services/chunking.py            # Only chunking
services/vector_store.py        # Only Milvus ops

❌ DON'T:
services/everything.py          # Multiple responsibilities
```

### 2. Clear Naming
```
✅ DO:
services/embedding_service.py   # Clear purpose
api/routes.py                   # Clear purpose
core/rag_pipeline.py           # Clear purpose

❌ DON'T:
services/helper.py             # Vague
api/stuff.py                   # Unclear
core/utils.py                  # Generic
```

### 3. Logical Grouping
```
✅ DO:
services/           # All services together
    ├─ parser.py
    ├─ chunking.py
    └─ embedding.py

❌ DON'T:
/                  # Everything mixed
├─ parser.py
├─ main.py
├─ chunking.py
└─ config.py
```

---

## 🔍 Quick Navigation Guide

### Want to find...

**API endpoints?**
→ `api/routes.py`

**Request/response models?**
→ `api/models.py`

**Main RAG logic?**
→ `core/rag_pipeline.py`

**Document parsing?**
→ `services/document_parser.py`

**Chunking logic?**
→ `services/chunking.py`

**Milvus operations?**
→ `services/vector_store.py`

**LLM integration?**
→ `services/llm_service.py`

**Configuration?**
→ `app/config.py`

**Application startup?**
→ `app/main.py`

**Database init?**
→ `scripts/init_milvus.py`

**Usage examples?**
→ `scripts/example_usage.py`

**Tests?**
→ `tests/test_basic.py`

**Documentation?**
→ `docs/` folder

---

## 📝 Cheat Sheet

### Common Tasks

**Start the app:**
```bash
python run.py
```

**Initialize Milvus:**
```bash
python run.py --init
```

**Run tests:**
```bash
python run.py --test
```

**Add a new service:**
1. Create `services/my_service.py`
2. Export in `services/__init__.py`
3. Use in `core/rag_pipeline.py`

**Add a new endpoint:**
1. Add model in `api/models.py`
2. Add route in `api/routes.py`
3. Test at `/docs`

**Import pattern:**
```python
from app.config import settings
from services.chunking import Chunk
from core.rag_pipeline import RAGPipeline
```

---

## ✨ Summary

This architecture provides:
- ✅ **Clear structure** - Easy to understand
- ✅ **Logical flow** - Top to bottom
- ✅ **Clean dependencies** - No circles
- ✅ **Easy navigation** - Know where to look
- ✅ **Scalable** - Room to grow

**Professional, maintainable, production-ready!** 🚀
