"""Health check endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    """Return application and database status."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
