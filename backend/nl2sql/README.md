# Customer Support NL2SQL

A production-ready **Natural Language to SQL** microservice for customer support bots.
Ask questions in plain English about your customer profiles and order history — the system converts them to SQL, executes against your synced Postgres database, and returns a human-readable answer.

Inspired by and derived from the accuracy patterns in [PrivyBot](https://github.com/privybot).

---

## Features

| Feature | Detail |
|---|---|
| **NL → SQL Pipeline** | Vector cache → full-schema SQL generation → retry |
| **Semantic SQL Cache** | pgvector cosine similarity; reuses proven queries above 0.92 threshold |
| **Self-Healing Retry** | Up to 3 retries feeding the SQL error back to the LLM |
| **Data Sync API** | Register any Postgres/MySQL/MSSQL source; maps columns automatically |
| **Cron Sync** | Background APScheduler job syncs all active sources every N minutes |
| **Security** | SQL injection blocklist + EXPLAIN dry-run before every execution |
| **Full Observability** | Every query logged with SQL, tokens, latency, retry count |

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- `uv`
- PostgreSQL 14+ with pgvector extension (`pgvector/pgvector:pg16` Docker image)
- OpenAI API key

### 2. Setup

```bash
# Clone / unzip the project
cd customer_support_nl2sql

# Copy environment config
cp .env.example .env
# Edit .env — set OPENAI_API_KEY and DB credentials

# Install dependencies
uv sync
```

### 3. Start with Docker (recommended)

```bash
# Start Postgres + app
docker-compose up -d

# The app is live at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### 4. Start without Docker

```bash
# Make sure Postgres is running and has the pgvector extension
psql -U postgres -c "CREATE DATABASE cs_nl2sql;"

# Run migrations
uv run alembic upgrade head

# Seed sample data (optional — for testing)
uv run python scripts/seed_sample_data.py

# Start the API server
uv run uvicorn app.main:app --reload --port 8000
```

---

## API Usage

### Ask a question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me all VIP customers in the USA",
    "session_id": "session-abc-123",
    "include_sql": true,
    "include_raw_data": true
  }'
```

**Response:**
```json
{
  "question": "Show me all VIP customers in the USA",
  "reframed_question": "List all customers with status 'vip' located in the USA",
  "nl_response": "I found 7 VIP customers in the USA. Here is the list.",
  "is_greeting": false,
  "rows": [ ... ],
  "total_count": 7,
  "sql_query": "SELECT ... FROM customers c WHERE c.status = 'vip' AND c.country ILIKE '%USA%' LIMIT 100;",
  "sql_source": "llm",
  "retry_count": 0,
  "token_usage": { "input_tokens": 412, "output_tokens": 89, "total_tokens": 501 },
  "latency_ms": 1243
}
```

### Register an external database

```bash
curl -X POST http://localhost:8000/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Store DB",
    "db_type": "postgresql",
    "host": "your-db-host.com",
    "port": 5432,
    "database_name": "store",
    "username": "readonly_user",
    "password": "your_password",
    "table_mapping": {
      "customers": "tbl_clients",
      "orders": "tbl_orders",
      "order_items": "tbl_order_lines"
    }
  }'
```

### Test a connection before saving

```bash
curl -X POST http://localhost:8000/datasources/test \
  -H "Content-Type: application/json" \
  -d '{ "db_type": "postgresql", "host": "...", "port": 5432, "database_name": "store", "username": "u", "password": "p" }'
```

### Trigger a manual sync

```bash
curl -X POST http://localhost:8000/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{ "source_id": "your-datasource-uuid" }'
```

### Check sync job status

```bash
curl http://localhost:8000/sync/jobs?source_id=your-datasource-uuid
```

---

## Sample Questions

The NL2SQL engine handles these and many more:

```
"Show me all VIP customers"
"How many orders were placed last month?"
"What is the total revenue from completed orders?"
"List the top 10 customers by lifetime value"
"Show all cancelled orders from this week"
"Which products were ordered most in Q1 2024?"
"Find customers who haven't ordered in 90 days"
"What is the average order value by country?"
"Show orders from Alice Smith"
"How many customers are inactive?"
"What is the revenue breakdown by payment method?"
"Show me all orders worth more than $500"
```

---

## Architecture

```
POST /query
     │
     ▼
NL2SQLEngine.query()
     │
     ├─ Step 1: Embed question (OpenAI text-embedding-3-small)
     │
     ├─ Step 2: Vector cache lookup (pgvector cosine similarity)
     │   ├─ similarity > 0.92 → reuse cached SQL (no LLM call)
     │   └─ otherwise → generate fresh SQL from full schema
     │
     ├─ Step 3: Execute SQL (with security checks + EXPLAIN dry-run)
     │
     ├─ Step 4: Retry on failure (up to 3x, full schema + error feedback)
     │
     ├─ Step 5: Build deterministic response locally
     │
     ├─ Step 6: Store successful pair in vector cache
     │
     └─ Step 7: Log everything to query_logs
```

---

## Project Structure

```
customer_support_nl2sql/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── query.py          ← POST /query (main NL2SQL endpoint)
│   │   │   ├── datasource.py     ← CRUD for external DB sources
│   │   │   ├── sync.py           ← Trigger / monitor syncs
│   │   │   ├── customers.py      ← Browse synced customers/orders
│   │   │   └── health.py         ← GET /health
│   │   └── schemas.py            ← All Pydantic request/response models
│   ├── core/
│   │   ├── nl2sql/
│   │   │   ├── engine.py         ← Main pipeline orchestrator ⭐
│   │   │   ├── prompts.py        ← All LLM prompt templates ⭐
│   │   │   ├── llm_client.py     ← OpenAI wrapper + SQL extractor
│   │   │   ├── sql_executor.py   ← Safe SQL execution + security
│   │   │   └── vector_cache.py   ← pgvector semantic cache
│   │   ├── schema/
│   │   │   └── schema_builder.py ← Schema strings for LLM prompts
│   │   └── sync/
│   │       ├── sync_engine.py    ← External DB → internal DB sync
│   │       └── scheduler.py      ← APScheduler cron job
│   ├── database/
│   │   └── connection.py         ← SQLAlchemy engine + session
│   ├── models/
│   │   └── tables.py             ← All ORM models
│   ├── utils/
│   │   └── encryption.py         ← AES password encryption
│   └── main.py                   ← FastAPI app factory
├── config/
│   └── settings.py               ← Pydantic settings from .env
├── migrations/                   ← Alembic migration scripts
├── scripts/
│   └── seed_sample_data.py       ← Insert test data
├── tests/
│   ├── test_nl2sql_engine.py     ← NL2SQL unit tests
│   └── test_sync_engine.py       ← Sync engine unit tests
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | SQL generation model |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model (1536 dims) |
| `INTERNAL_DB_HOST` | `localhost` | Postgres host |
| `INTERNAL_DB_PORT` | `5432` | Postgres port |
| `INTERNAL_DB_NAME` | `cs_nl2sql` | Internal database name |
| `VECTOR_SIMILARITY_THRESHOLD` | `0.92` | Cache reuse cutoff (0.0–1.0) |
| `MAX_SQL_RETRIES` | `3` | Max retry attempts on SQL failure |
| `MAX_ROWS_RETURNED` | `100` | Hard cap on result rows |
| `SYNC_CRON_INTERVAL_MINUTES` | `30` | How often cron sync runs |
| `SYNC_BATCH_SIZE` | `500` | Rows per insert batch during sync |

---

## Running Tests

```bash
uv run pytest tests/ -v
```

All tests are pure unit tests — no database or OpenAI key required.

---

## Accuracy Techniques (from PrivyBot)

1. **Semantic SQL cache** — proven queries reused at >0.92 cosine similarity
2. **Question reframing** — LLM resolves pronouns/abbreviations before SQL generation
3. **Schema narrowing** — only relevant tables injected into the prompt
4. **Chart-aware SQL** — aggregation hints based on likely visualization type
5. **Conversation history** — last 4 turns for follow-up question context
6. **Self-healing retry** — error message fed back to LLM for SQL repair
7. **EXPLAIN dry-run** — validates SQL syntax before real execution
8. **Security blocklist** — 15+ patterns block all mutation/injection attempts
9. **Full schema fallback** — broader context on retry attempts
10. **Vector-adapt mode** — adapts near-match cached SQL instead of regenerating
