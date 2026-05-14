#!/bin/sh
set -eu

echo "Starting seed check..."
uv run python scripts/seed_sample_data.py

echo "Starting API server..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
