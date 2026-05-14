"""
app/api/routes/datasource.py
────────────────────────────────────────────────────────────────────────────
CRUD for DataSource records + connection test endpoint.

POST   /datasources           — register a new external DB
GET    /datasources           — list all registered sources
GET    /datasources/{id}      — get one source
DELETE /datasources/{id}      — remove a source
POST   /datasources/test      — test credentials without saving
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import (
    DataSourceCreate, DataSourceResponse, DataSourceTestRequest, DataSourceTestResponse,
    SuccessResponse,
)
from app.database.connection import get_db
from app.models.tables import DataSource
from app.utils.encryption import encrypt_password

router = APIRouter(prefix="/datasources", tags=["Data Sources"])
logger = logging.getLogger(__name__)


@router.post("", response_model=DataSourceResponse, status_code=201)
def create_datasource(payload: DataSourceCreate, db: Session = Depends(get_db)):
    """
    Register a new external database as a sync source.
    The password is AES-encrypted before storage.
    """
    encrypted_pw = encrypt_password(payload.password)
    source = DataSource(
        name=payload.name,
        db_type=payload.db_type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        password_encrypted=encrypted_pw,
        schema_name=payload.schema_name,
        table_mapping=payload.table_mapping,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    logger.info("DataSource created: %s (%s)", source.name, source.id)
    return source


@router.get("", response_model=list[DataSourceResponse])
def list_datasources(db: Session = Depends(get_db)):
    return db.query(DataSource).filter_by(is_active=True).all()


@router.get("/{source_id}", response_model=DataSourceResponse)
def get_datasource(source_id: UUID, db: Session = Depends(get_db)):
    source = db.query(DataSource).filter_by(id=source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="DataSource not found")
    return source


@router.delete("/{source_id}", response_model=SuccessResponse)
def delete_datasource(source_id: UUID, db: Session = Depends(get_db)):
    source = db.query(DataSource).filter_by(id=source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="DataSource not found")
    source.is_active = False      # soft delete
    db.commit()
    return SuccessResponse(message="DataSource deactivated")


@router.post("/test", response_model=DataSourceTestResponse)
def test_datasource_connection(payload: DataSourceTestRequest):
    """
    Test that the provided credentials can connect to the source database.
    Lists the first 20 table names found.
    """
    from app.core.sync.sync_engine import _build_source_url
    from sqlalchemy import create_engine, inspect, text

    # Build a temporary DataSource-like object for URL building
    class _TempSource:
        db_type = payload.db_type
        username = payload.username
        host = payload.host
        port = payload.port
        database_name = payload.database_name

    url = _build_source_url(_TempSource(), payload.password)
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            inspector = inspect(engine)
            tables = inspector.get_table_names(schema=payload.schema_name or None)[:20]
        engine.dispose()
        return DataSourceTestResponse(
            success=True,
            message="Connection successful",
            tables_found=tables,
        )
    except Exception as exc:
        return DataSourceTestResponse(
            success=False,
            message=f"Connection failed: {str(exc)[:300]}",
        )
