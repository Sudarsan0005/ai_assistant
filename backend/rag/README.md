# RAG Service

This service ingests documents, stores chunk embeddings in Qdrant, retrieves relevant chunks, and generates grounded answers through a LangChain-selected LLM provider.

## Architecture

- `app/`: configuration and FastAPI bootstrap
- `api/`: HTTP models and routes
- `core/`: `RAGPipeline` orchestration
- `services/document_parser.py`: PDF, DOCX, text, markdown, image parsing
- `services/chunking.py`: token, semantic, and hierarchical chunking
- `services/embedding_service.py`: sentence-transformer embeddings
- `services/vector_store.py`: Qdrant single-collection storage
- `services/retrieval_service.py`: hybrid retrieval and citation handling
- `services/llm_service.py`: LangChain chat-model routing by env

## Design Changes

### 1. Qdrant replaces Milvus

The service no longer keeps a separate document-metadata collection. Each chunk payload now stores:

- `doc_id`
- `filename`
- `file_type`
- `page_number`
- `chunk_index`
- `position`
- chunk-level `metadata`
- document-level `document_metadata`

That fixes the earlier design issue where retrieving a chunk did not guarantee that page/source metadata was available in the same record.

### 2. Single-record chunk payloads

When chunk `56` is retrieved, the result already includes:

- the document id
- the filename
- the page number
- the chunk index
- layout position
- file type
- source metadata

Document listing and stats are derived by aggregating chunk payloads by `doc_id`.

### 3. LangChain-based model routing

Set `LLM_PROVIDER` in `.env` to switch providers without code changes:

- `openai`
- `openai_compatible`
- `anthropic`
- `ollama`
- `nvidia`

## Environment

Copy the example file:

```bash
cp .env.example .env
```

Common settings:

```env
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=document_chunks

LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your_key
```

For Ollama:

```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
```

For NVIDIA:

```env
LLM_PROVIDER=nvidia
LLM_MODEL=meta/llama-3.1-70b-instruct
NVIDIA_API_KEY=your_key
```

## Local Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Start Qdrant:

```bash
docker-compose up -d qdrant
```

Initialize the collection:

```bash
python run.py --init
```

Start the API:

```bash
python run.py
```

Open:

```text
http://localhost:8000/docs
```

## Docker Run

```bash
docker-compose up --build
```

This starts:

- `qdrant` on `6333`
- `app` on `8000`

## API

Health:

```bash
curl http://localhost:8000/
```

Upload:

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@/path/to/document.pdf" \
  -F "chunking_strategy=token"
```

Query:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main conclusions?",
    "use_citations": true
  }'
```

## Retrieval Notes

The retrieval path is:

1. Parse and chunk the document.
2. Embed chunks with a sentence-transformer model.
3. Store vectors plus full chunk payloads in Qdrant.
4. Embed the user query.
5. Run vector search and lightweight keyword re-ranking.
6. Build compact citation-aware context.
7. Generate the answer through the configured LangChain model.

## Accuracy and Latency

Accuracy improvements:

- full source metadata on every chunk
- hybrid retrieval with keyword-aware re-ranking
- citation-aware prompting
- document filtering by `doc_ids`

Latency improvements:

- no second metadata lookup after retrieval
- single Qdrant collection
- light in-process hybrid re-ranking instead of multi-store joins
- provider switching without custom client branches in the pipeline
