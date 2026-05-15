# Quick Start Guide

## Prerequisites Check

Before starting, ensure you have:
- [ ] Python 3.8 or higher installed
- [ ] Docker and Docker Compose installed
- [ ] At least 8GB RAM available
- [ ] OpenAI API key (or Anthropic API key)

## Installation Steps

### 1. Extract and Navigate
```bash
unzip rag_application.zip
cd rag_app
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API key
nano .env  # or use your preferred editor
```

**Required:** Set at least one of these:
- `OPENAI_API_KEY=sk-...`
- `ANTHROPIC_API_KEY=sk-ant-...`

### 4. Start Milvus Vector Database
```bash
docker-compose up -d
```

Wait for ~30 seconds for Milvus to initialize.

Check status:
```bash
docker-compose ps
```

All services should show "Up (healthy)".

### 5. Start the Application

**Option A: Using the startup script (recommended)**
```bash
chmod +x start.sh
./start.sh
```

**Option B: Direct Python**
```bash
python main.py
```

### 6. Test the API

Open your browser and go to:
- API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs

## First Test

### Using Python Client
```python
from api_client import RAGClient

# Initialize
client = RAGClient()

# Check health
print(client.health_check())

# Upload a document (create a test file first)
with open("test.txt", "w") as f:
    f.write("This is a test document about RAG systems.")

doc = client.upload_document("test.txt")
print(f"Uploaded: {doc['doc_id']}")

# Query
response = client.query("What is this about?")
print(response['answer'])
```

### Using cURL
```bash
# Upload document
curl -X POST "http://localhost:8000/documents/upload" \
  -F "file=@test.txt"

# Query
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this about?", "use_citations": true}'
```

## Common Issues

### Milvus won't start
```bash
# Clean up and restart
docker-compose down -v
docker-compose up -d
```

### Port 8000 already in use
```bash
# Change port in main.py or use:
python main.py --port 8001
```

### Module not found errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Out of memory
- Reduce `EMBEDDING_BATCH_SIZE` in .env
- Use a smaller embedding model: `sentence-transformers/all-MiniLM-L6-v2`

## Next Steps

1. **Read the Full README**: See `README.md` for detailed documentation
2. **Run Examples**: `python example_usage.py`
3. **Run Tests**: `python test_basic.py`
4. **Explore API Docs**: http://localhost:8000/docs

## Quick Reference

### Key Files
- `main.py` - FastAPI application
- `rag_pipeline.py` - Core RAG logic
- `config.py` - Configuration
- `.env` - Environment variables

### Key Endpoints
- `POST /documents/upload` - Upload document
- `POST /query` - Ask questions
- `GET /documents` - List documents
- `DELETE /documents/{id}` - Delete document

### Stopping the Application

1. Stop the API: Press Ctrl+C
2. Stop Milvus: `docker-compose down`

## Support

If you encounter issues:
1. Check the troubleshooting section in README.md
2. Enable DEBUG mode in .env: `DEBUG=True`
3. Check logs in the console output

## What's Next?

- Upload your own PDFs, DOCX, or text files
- Try different chunking strategies
- Experiment with citation management
- Build your own RAG application!

---

**Happy Building! 🚀**
