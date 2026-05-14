"""
app/api/routes/sync.py
─────────────────────────────────────────────────────────────────────────────
Sync management endpoints.

POST /sync/trigger         — manually trigger a sync for a source
GET  /sync/jobs            — list recent sync jobs
GET  /sync/jobs/{id}       — get one sync job detail
"""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import SyncJobResponse, SyncTriggerRequest, SuccessResponse
from app.database.connection import get_db
from app.models.tables import DataSource, SyncJob
from app.utils.encryption import decrypt_password

router = APIRouter(prefix="/sync", tags=["Sync"])
logger = logging.getLogger(__name__)


def _run_sync_background(source_id: UUID, plain_password: str):
    """Background task function for manual sync trigger."""
    from app.database.connection import db_session
    from app.core.sync.sync_engine import SyncEngine

    with db_session() as db:
        engine = SyncEngine(db)
        try:
            stats = engine.run(source_id=source_id, plain_password=plain_password, triggered_by="manual")
            logger.info("Manual sync completed for source %s: %s", source_id, stats)
        except Exception as exc:
            logger.error("Manual sync failed for source %s: %s", source_id, exc)


@router.post("/trigger", response_model=SuccessResponse, status_code=202)
def trigger_sync(
    payload: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Manually trigger a data sync for the specified source.
    The sync runs in the background — poll /sync/jobs for status.
    """
    source = db.query(DataSource).filter_by(id=payload.source_id, is_active=True).first()
    if not source:
        raise HTTPException(status_code=404, detail="DataSource not found or inactive")

    try:
        plain_password = decrypt_password(source.password_encrypted)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    background_tasks.add_task(_run_sync_background, source.id, plain_password)
    return SuccessResponse(message="Sync triggered — running in background")


@router.get("/jobs", response_model=list[SyncJobResponse])
def list_sync_jobs(
    source_id: UUID = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List recent sync jobs, optionally filtered by source."""
    q = db.query(SyncJob).order_by(SyncJob.started_at.desc())
    if source_id:
        q = q.filter(SyncJob.source_id == source_id)
    return q.limit(limit).all()


@router.get("/jobs/{job_id}", response_model=SyncJobResponse)
def get_sync_job(job_id: UUID, db: Session = Depends(get_db)):
    job = db.query(SyncJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return job
