"""
app/core/sync/scheduler.py
──────────────────────────
APScheduler-based cron job that periodically syncs all active data sources.

The scheduler is started when the FastAPI app starts up and stopped on shutdown.
The interval is controlled by SYNC_CRON_INTERVAL_MINUTES in settings.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: Optional[BackgroundScheduler] = None


def _run_all_sources():
    """Job function — called by APScheduler on each tick."""
    from app.database.connection import db_session
    from app.core.sync.sync_engine import SyncEngine
    from app.models.tables import DataSource
    from app.utils.encryption import decrypt_password

    logger.info("Cron sync started at %s", datetime.now(timezone.utc).isoformat())

    with db_session() as db:
        sources = db.query(DataSource).filter_by(is_active=True).all()
        if not sources:
            logger.info("No active data sources — nothing to sync")
            return

        for source in sources:
            try:
                plain_password = decrypt_password(source.password_encrypted)
                engine = SyncEngine(db)
                stats = engine.run(
                    source_id=source.id,
                    plain_password=plain_password,
                    triggered_by="cron",
                )
                logger.info("Cron sync OK for source '%s': %s", source.name, stats)
            except Exception as exc:
                logger.error("Cron sync FAILED for source '%s': %s", source.name, exc)


def start_scheduler():
    """Start the background sync scheduler. Called on app startup."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        func=_run_all_sources,
        trigger=IntervalTrigger(minutes=settings.sync_cron_interval_minutes),
        id="data_sync",
        name="Sync all active data sources",
        replace_existing=True,
        max_instances=1,         # never run two syncs simultaneously
        coalesce=True,           # skip missed runs instead of catching up
    )
    _scheduler.start()
    logger.info(
        "Sync scheduler started — interval=%d min",
        settings.sync_cron_interval_minutes,
    )


def stop_scheduler():
    """Stop the scheduler. Called on app shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Sync scheduler stopped")
