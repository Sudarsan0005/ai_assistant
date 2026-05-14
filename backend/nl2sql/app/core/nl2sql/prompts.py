"""
app/core/nl2sql/prompts.py
──────────────────────────
All LLM prompt templates for the NL2SQL pipeline.
Keeping them in one file makes tuning easy without touching logic code.
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL GENERATION
# ─────────────────────────────────────────────────────────────────────────────

SQL_GENERATION_PROMPT = """You are an expert PostgreSQL query generator for a customer support system.

DATABASE SCHEMA:
{database_schema}

BUSINESS RULES:
{custom_rules}

IMPORTANT INSTRUCTIONS:
- The user is always asking a database question about this schema.
- Respond with valid JSON only: {{"sql": "SELECT ...;"}}.
- Generate exactly one SELECT statement. Never use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE.
- Always qualify column names with table aliases to avoid ambiguity.
- Use ILIKE for case-insensitive string matching.
- For date filters, use proper PostgreSQL date functions (DATE_TRUNC, NOW(), INTERVAL).
- Always add a LIMIT clause — maximum {max_rows} rows.
- If joining customers and orders, use: customers c JOIN orders o ON o.customer_id = c.id
- If joining orders and order_items, use: orders o JOIN order_items oi ON oi.order_id = o.id
- Do not include any explanation, markdown, or extra keys.

User question: {question}
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL GENERATION (fallback — full schema, used on retry)
# ─────────────────────────────────────────────────────────────────────────────

SQL_GENERATION_FULL_SCHEMA_PROMPT = """You are an expert PostgreSQL query generator for a customer support system.

FULL DATABASE SCHEMA:
{database_schema}

PREVIOUS FAILED QUERY:
{failed_query}

EXECUTION ERROR:
{error_message}

BUSINESS RULES:
{custom_rules}

IMPORTANT INSTRUCTIONS:
- The previous query above FAILED with the error shown. Fix it.
- Respond with valid JSON only: {{"sql": "SELECT ...;"}}.
- Generate ONLY a corrected SELECT statement.
- Never use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, INFORMATION_SCHEMA.
- Always qualify column names with table aliases.
- Use ILIKE for case-insensitive text matching.
- Always add LIMIT {max_rows}.
- Do not include any explanation, markdown, or extra keys.

User question: {question}
"""

NO_DATA_DEFAULT = (
    "I couldn't find any matching records for your query. "
    "Please check the details and try again, or contact support for further help."
)
