"""
app/main.py
────────────────────────────────────────────────────────────────────────────
FastAPI application factory.

Startup sequence:
  1. Initialize database (create tables, enable pgvector extension)
  2. Register all API routers
  3. Start background sync scheduler

Shutdown sequence:
  1. Stop background scheduler
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import customers, datasource, health, query, sync
from app.core.sync.scheduler import start_scheduler, stop_scheduler
from app.database.connection import init_db
from config.settings import get_settings

settings = get_settings()
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting %s [%s]", settings.app_name, settings.app_env)
    init_db()
    logger.info("Database initialized")
    start_scheduler()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    stop_scheduler()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Customer Support NL2SQL — convert natural language questions about "
            "customers and orders into SQL and return human-readable answers."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(query.router)
    app.include_router(datasource.router)
    app.include_router(sync.router)
    app.include_router(customers.router)

    return app


app = create_app()
