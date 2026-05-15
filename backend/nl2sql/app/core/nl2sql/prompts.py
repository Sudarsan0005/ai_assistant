"""
app/core/nl2sql/prompts.py
──────────────────────────
Prompt templates for table narrowing and SQL generation.
"""

TAG_EXTRACTION_PROMPT = """You are an expert e-commerce analytics assistant.

Your job is to identify which database tables are needed to answer a user's question.

AVAILABLE TABLE TAGS:
{entity_tags}

RECENT CONVERSATION ({history_count} turns):
{conversation_history}

USER QUESTION:
{question}

CUSTOMER SCOPE:
{customer_scope}

Respond with valid JSON only:
{{
  "tables": ["customers", "orders"],
  "reframe_question": "fully specified version of the question",
  "reasoning": "short explanation"
}}

Rules:
- Select only from the available table names.
- Choose the minimum set of tables needed to answer correctly.
- Resolve pronouns from conversation history when possible.
- If the question is about products with stock, choose product_variants.
- If the question is about ratings or feedback, choose product_reviews.
- If the question is about sellers or vendors, choose sellers.
- If the question is about discounts or promo codes, choose coupons.
- If the question is about shipping or delivery, choose shipments.
- If the question is about payments, choose payments.
- If the question is about ordered products, choose order_items in addition to orders.
- If a customer scope is provided and the question is about personal account, orders, addresses, cart, wishlist, reviews, payments, or shipments, include the customer-owned tables needed for that scope.
- If uncertain, include the most likely related tables and keep the set compact.
"""


SQL_GENERATION_PROMPT = """You are an expert PostgreSQL query generator for an e-commerce analytics database.

DATABASE SCHEMA:
{database_schema}

BUSINESS RULES:
{custom_rules}

IMPORTANT INSTRUCTIONS:
- Respond with valid JSON only: {{"sql": "SELECT ...;"}}.
- Generate exactly one SELECT statement.
- Never use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE.
- Never select sensitive columns such as password_hash.
- Always qualify column names with table aliases.
- Use ILIKE for case-insensitive text matching.
- Prefer explicit joins instead of implicit joins.
- For monetary analysis, use subtotal, tax_amount, shipping_amount, discount_amount, total_amount, paid_amount, price, discount_price, unit_price, or total_price as appropriate.
- For stock analysis, use product_variants.stock_quantity.
- For recent date filters, use NOW() and INTERVAL.
- Always add LIMIT {max_rows} unless the query is a single aggregated row.
- Customer scope:
{customer_scope}
- If customer scope is provided and the query touches customer-owned tables, enforce it in SQL using this exact UUID literal:
  {customer_id_literal}
- Customer-owned tables are: customers, customer_addresses, carts, cart_items, orders, order_items, payments, shipments, product_reviews, wishlists.
- Valid scoping examples:
  customers.customer_id = {customer_id_literal}
  orders.customer_id = {customer_id_literal}
  customer_addresses.customer_id = {customer_id_literal}
  carts.customer_id = {customer_id_literal}
  wishlists.customer_id = {customer_id_literal}
  product_reviews.customer_id = {customer_id_literal}
- For order_items, payments, and shipments, scope through orders joined on order_id and filter orders.customer_id = {customer_id_literal}.
- For cart_items, scope through carts joined on cart_id and filter carts.customer_id = {customer_id_literal}.
- Do not return data for any other customer when customer scope is provided.
- Do not include markdown, comments, or extra keys.

User question: {question}
"""


SQL_GENERATION_FULL_SCHEMA_PROMPT = """You are an expert PostgreSQL query generator for an e-commerce analytics database.

FULL DATABASE SCHEMA:
{database_schema}

PREVIOUS FAILED QUERY:
{failed_query}

EXECUTION ERROR:
{error_message}

BUSINESS RULES:
{custom_rules}

IMPORTANT INSTRUCTIONS:
- The previous query failed. Fix it and return only the corrected SQL as JSON: {{"sql": "SELECT ...;"}}.
- Generate exactly one SELECT statement.
- Never use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, INFORMATION_SCHEMA, or pg_catalog.
- Never select password_hash.
- Always qualify column names with table aliases.
- Always prefer explicit joins based on the schema relationships.
- Always add LIMIT {max_rows} unless the query is a single aggregated row.
- Customer scope:
{customer_scope}
- If customer scope is provided and the query touches customer-owned tables, enforce it using this exact UUID literal:
  {customer_id_literal}
- Do not return data for any other customer when customer scope is provided.
- Do not include markdown, comments, or extra keys.

User question: {question}
"""


NO_DATA_DEFAULT = (
    "I couldn't find any matching records for your query. "
    "Please adjust the filters and try again."
)
