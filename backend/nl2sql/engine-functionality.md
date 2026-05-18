# Engine Functionality

This document explains how the NL2SQL engine is designed, how queries are generated, which techniques are used to improve latency and accuracy, and which engineering challenges came up while building the service. It is written for business discussions, architecture reviews, and interview conversations.

## 1. What This Engine Does

The engine converts a natural-language question into a safe SQL query over an internal e-commerce warehouse.

It is designed for a chatbot or assistant use case where:

- a user asks questions in plain English
- the system maps the question to the correct subset of tables
- SQL is generated and executed safely
- results are returned quickly
- customer-scoped data can be enforced when the request comes from a logged-in customer

The current schema supports a broad e-commerce domain:

- customers
- addresses
- sellers
- categories
- products
- product variants
- images
- attributes
- carts
- orders
- payments
- shipments
- reviews
- wishlists
- coupons

This is no longer a generic demo-only NL2SQL service. It is shaped around a real e-commerce analytics and customer-support use case.

## 2. High-Level Request Flow

The current flow is:

1. The API receives a question through `POST /query`.
2. Optional `session_id` is used for conversational continuity.
3. Optional `customer_id` is used for customer-level data restriction.
4. The engine first narrows the relevant tables.
5. The engine embeds the reframed question.
6. It checks the vector cache for a semantically similar successful SQL query.
7. If no strong cache hit exists, it asks the LLM to generate SQL using a narrowed schema.
8. The SQL is validated and executed safely.
9. If execution fails, the engine retries with the full schema and error feedback.
10. Results are returned in a deterministic response format.
11. Successful query/SQL pairs are stored in the vector cache.
12. The request is logged for traceability and session history.

## 3. How Query Generation Works

### 3.1 Table narrowing first

The database now has many tables, so sending the full schema to the model for every request increases both latency and confusion.

To avoid that, the engine first performs a narrowing step:

- the engine uses a table-tag dictionary
- each table is mapped to domain words such as `orders`, `payments`, `wishlist`, `seller`, `delivery`, `stock`, `reviews`
- an LLM JSON step selects the minimum likely table set for the question
- dependency expansion then adds required related tables automatically

Example:

- "show low stock variants by seller"
  becomes something like:
  `product_variants`, `products`, `sellers`

- "show my last 5 delivered orders"
  becomes something like:
  `orders`, `shipments`, and sometimes `customers`

This narrowing step improves accuracy because the model sees less irrelevant schema and is less likely to join unrelated tables.

### 3.2 SQL generation from narrowed schema

After narrowing:

- the engine builds a human-readable schema prompt
- it includes only the relevant tables plus join guidance
- it asks the LLM to return structured JSON containing SQL
- the LLM is instructed to produce one `SELECT` statement only

This is more reliable than free-form output because:

- the response format is constrained
- SQL extraction is simpler
- the engine can validate customer scoping rules before execution

### 3.3 Retry with full schema

If the first generated SQL fails:

- the engine passes the failed query and database error back to the LLM
- it expands to the full schema
- it asks for a corrected query

This is a recovery path, not the default path.

Business reason:

- first-pass latency remains lower because most requests use narrowed schema
- difficult cases still have a fallback path instead of hard-failing immediately

## 4. Customer-Specific Data Enforcement

One important business requirement is that a logged-in customer must see only their own data.

That is why the request supports:

- `session_id` for conversation continuity
- `customer_id` for access control and row scoping

These two serve different purposes.

### 4.1 Why `session_id` exists

`session_id` is memory, not security.

It helps with follow-up questions like:

- "show my last 5 delivered orders"
- "what about the latest one"
- "did I pay by UPI"

Without `session_id`, the engine would lose conversational continuity.

### 4.2 Why `customer_id` exists

`customer_id` is the enforcement mechanism.

If a question touches customer-owned tables such as:

- customers
- addresses
- carts
- orders
- payments
- shipments
- reviews
- wishlists

the engine requires the SQL to contain that customer scope.

This is important because the text "I am Noah Miller" is not trustworthy as identity.

The system should trust:

- authenticated customer ID from the calling application

not:

- natural language self-claims from the prompt

### 4.3 Practical security model

The current design uses prompt-time restriction plus engine-side validation:

- prompts instruct the model to scope customer-owned data to the provided `customer_id`
- generated SQL is checked before execution
- unscoped SQL touching customer-owned tables is rejected and retried

This design gives a pragmatic balance between:

- business flexibility
- multi-turn chatbot UX
- safety against accidental cross-customer leakage

## 5. Techniques Used to Reduce Latency

Latency matters because this service is chat-facing.

### 5.1 Narrow schema instead of full schema by default

This is one of the biggest wins.

Why it helps:

- fewer tokens
- smaller prompts
- less ambiguity for the model
- lower cost and lower generation time

### 5.2 Semantic vector cache

The engine stores successful NL-to-SQL pairs along with embeddings.

For a similar future question:

- the engine can reuse the previous SQL directly if similarity is high enough

Example:

- "show my recent delivered orders"
- "show my last delivered purchases"

If the cached query is semantically close, a full generation step can be skipped.

This reduces:

- LLM latency
- token cost
- repeated generation errors on common questions

### 5.3 Deterministic response formatting

The engine currently avoids a second LLM call for natural-language phrasing.

Instead:

- single-value results are formatted directly
- list results return a compact deterministic message

This reduces:

- one entire LLM round-trip
- response variability
- cost per query

### 5.4 Retry only on failure

The full-schema correction flow is only used when necessary.

That means:

- fast path stays fast
- expensive recovery path is reserved for difficult cases

## 6. Techniques Used to Improve Accuracy

### 6.1 Domain-specific schema design

A general-purpose schema is harder for an LLM to reason about.

This design uses:

- clear business tables
- meaningful relationships
- consistent naming like `customer_id`, `order_id`, `variant_id`
- snapshot-style `order_items`

That last part is especially important in business systems.

For example:

- `order_items` stores product and variant details at purchase time
- queries on historical sales do not break when current product metadata changes later

This is both a data-modeling decision and an NL2SQL accuracy decision.

### 6.2 Join guidance in prompts

The schema builder does not only list columns.

It also provides join guidance.

This reduces common model mistakes like:

- joining unrelated keys
- missing a bridge table
- filtering on the wrong entity

### 6.3 Structured JSON outputs

The model is asked to return JSON with SQL, not mixed explanations.

This improves reliability because:

- parsing is simpler
- prompt drift is lower
- retries are easier to handle programmatically

### 6.4 Safe execution and `EXPLAIN`

Before execution:

- mutating SQL is blocked
- `EXPLAIN` is used as a dry run
- row limits are enforced

This improves production accuracy indirectly because:

- broken SQL is caught earlier
- retries get concrete database feedback

### 6.5 Session-based context

Follow-up questions are a real business need.

Session history helps resolve:

- pronouns
- ellipsis
- follow-up filters

That improves the quality of multi-turn chatbot behavior without needing a separate conversation service.

## 7. Why the Table Structure Matters

From a business and product perspective, the table structure was designed around actual e-commerce questions.

Examples:

- Customer support:
  "Where is my order?"
  "Was my payment successful?"
  "Which address did I use?"

- Product analytics:
  "Which categories drive the most revenue?"
  "Which variants are low in stock?"
  "Which sellers have the highest rated products?"

- Growth and retention:
  "Which customers abandoned carts?"
  "What products are most wishlisted?"
  "Which coupons are active and effective?"

The schema separates concerns clearly, which helps:

- product teams ask better questions
- analytics stay trustworthy
- the LLM has clearer semantic boundaries

## 8. Key Challenges Faced So Far

### 8.1 Moving from a demo schema to a business schema

The initial 3-table customer-order demo was simple, but it was not sufficient for real e-commerce behavior.

The challenge was not only adding more tables.

The bigger challenge was:

- preserving query accuracy as schema complexity increased

That is why table narrowing became necessary.

### 8.2 Balancing latency against accuracy

If the engine always sees the full schema:

- accuracy can drop due to too much context
- latency and token cost go up

If the engine narrows too aggressively:

- it may exclude required tables

So the challenge is designing a narrowing layer that is:

- compact enough for speed
- broad enough for correctness

### 8.3 Customer scoping versus analytics flexibility

A customer chatbot should not expose another user's data.

But the same system may also need global catalog questions like:

- "which sellers have the highest average product rating?"

The design challenge is deciding when to enforce customer scope and when a question is legitimately global.

This is both:

- a security design problem
- a product-definition problem

### 8.4 Transaction-state bugs in long request flows

One non-obvious issue was transaction state.

If an earlier DB operation fails and the session is not rolled back:

- later SQL may fail with `current transaction is aborted`

This can be confusing because the final SQL may be perfectly valid.

This kind of bug shows that NL2SQL systems are not only prompt-engineering problems. They are also classic production engineering systems with database session management issues.

### 8.5 Seeding realistic test data

Simple random data is usually not enough.

For NL2SQL to be evaluated properly, sample data needs:

- relational consistency
- realistic product names and attributes
- realistic payment and delivery states
- enough row volume to exercise joins and aggregations

This is why the seed design became part of the product quality discussion, not just a developer convenience.

## 9. Interview Discussion Points

If this comes up in an interview, strong discussion points are:

### 9.1 Why not always use the full schema?

Because larger schema context increases latency, cost, and ambiguity.

The better design is:

- narrow first
- expand only on failure

That is a practical tradeoff between performance and correctness.

### 9.2 Why use `customer_id` in addition to `session_id`?

Because:

- `session_id` is conversational context
- `customer_id` is access control

Treating those as the same concern is a design mistake.

### 9.3 Why keep a vector cache?

Because user questions are repetitive in production.

Caching successful NL-to-SQL pairs:

- reduces cost
- reduces latency
- improves consistency on frequent questions

### 9.4 Why keep retry logic?

Because real NL2SQL systems are probabilistic.

Even good prompts can generate:

- wrong joins
- ambiguous filters
- column mistakes

Retry with database error feedback gives the system a self-correction loop.

### 9.5 Why use deterministic answer formatting?

Because this microservice’s primary job is SQL generation and safe retrieval, not polished conversational prose.

Removing unnecessary LLM calls:

- lowers cost
- lowers latency
- reduces failure surface

## 10. Business Positioning Summary

From a business perspective, this engine is valuable because it turns an internal warehouse into a conversational interface without forcing every user to know SQL.

Its design priorities are:

- safe access to data
- customer-level restriction where required
- good enough conversational continuity
- low enough latency for chatbot use
- enough schema awareness to answer real e-commerce questions

From an engineering perspective, the important architectural ideas are:

- table narrowing before SQL generation
- semantic caching
- customer-scope enforcement
- safe execution with retries
- domain-specific schema design

That combination is what makes the service more than a generic prompt wrapper. It is an application-specific NL2SQL engine aligned with a real business use case.
