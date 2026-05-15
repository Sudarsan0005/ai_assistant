# E-commerce NL2SQL

An NL2SQL microservice for an internal e-commerce warehouse. It answers natural-language questions over customers, products, variants, carts, orders, payments, shipments, reviews, wishlists, coupons, sellers, categories, and related tables.

## Highlights

- 18 business tables tailored to an e-commerce marketplace schema
- Table-tag narrowing before SQL generation for better accuracy on a larger schema
- pgvector SQL cache for repeated questions
- Safe SQL execution with blocklist checks, `EXPLAIN`, retry, and row limits
- Docker startup that seeds realistic sample data automatically when the DB is empty

## Active API

- `GET /health`
- `POST /query`
- `GET /query/history`

## Local Run

```bash
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run python scripts/seed_sample_data.py
uv run uvicorn app.main:app --reload --port 8000
```

## Docker Run

```bash
docker-compose up --build
```

On first startup, the app seeds sample e-commerce data automatically if the business tables are empty.

## Sample Questions

```text
Show the top 10 customers by total order value
Which sellers have the highest average product rating?
List low-stock variants for active products
How many delivered orders were paid by UPI last month?
What are the top product categories by revenue?
Show products with the most wishlist adds
Which coupons are currently active?
Find customers with abandoned carts in the last 7 days
What is the average delivery time by courier?
Show the highest-rated products in Electronics
```

## Schema Areas

- `customers`, `customer_addresses`
- `categories`, `sellers`, `products`, `product_variants`, `product_images`
- `attributes`, `product_attribute_values`
- `carts`, `cart_items`
- `orders`, `order_items`
- `payments`, `shipments`
- `product_reviews`, `wishlists`, `coupons`
- `query_cache`, `query_sessions`, `query_logs`
