from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.session import get_db
from app.models.source import Source, Organization
from app.models.notification import DiscoveryLog, Notification
from app.schemas.source import (
    SourceSchema, SourceStatusResponse, DiscoveryStatusResponse, OrganizationSchema
)
from app.services.discovery import DiscoveryEngine

router = APIRouter(prefix="/api/v1", tags=["sources"])


def verify_admin_access(request: Request):
    """Ensure endpoint is called locally or with authorized admin credentials."""
    client_host = request.client.host if request.client else ""
    auth_header = request.headers.get("x-admin-key", "")
    is_local = client_host in ("127.0.0.1", "localhost", "::1", "testclient")
    if not is_local and auth_header != "examradar-admin":
        raise HTTPException(
            status_code=403,
            detail="Unauthorized. Discovery trigger is restricted to local development or authorized administrators."
        )


@router.get("/sources", response_model=list[SourceSchema])
def get_sources(db: Session = Depends(get_db)):
    sources = db.query(Source).all()
    result = []
    for s in sources:
        org = db.query(Organization).filter(Organization.id == s.organization_id).first()
        notif_count = db.query(Notification).filter(
            Notification.organization_id == s.organization_id,
            Notification.is_synthetic == False,
        ).count()
        schema = SourceSchema(
            id=s.id,
            name=s.name,
            base_url=s.base_url,
            recruitment_page_url=s.recruitment_page_url,
            organization_id=s.organization_id,
            organization_name=org.name if org else None,
            category=s.category.value,
            source_type=s.source_type.value,
            is_enabled=s.is_enabled,
            fetch_interval_minutes=s.fetch_interval_minutes,
            last_successful_check=s.last_successful_check,
            last_discovered_at=s.last_discovered_at,
            last_error=s.last_error,
            last_error_at=s.last_error_at,
            error_count=s.error_count,
            notifications_count=notif_count,
            parsing_strategy=s.parsing_strategy,
            robots_txt_allowed=s.robots_txt_allowed,
        )
        result.append(schema)
    return result


@router.get("/sources/status", response_model=SourceStatusResponse)
@router.get("/source-status", response_model=SourceStatusResponse)
def get_source_status(db: Session = Depends(get_db)):
    total = db.query(Source).count()
    enabled = db.query(Source).filter(Source.is_enabled == True).count()
    with_errors = db.query(Source).filter(Source.error_count > 0).count()
    last_run = db.query(func.max(DiscoveryLog.started_at)).scalar()

    sources = db.query(Source).all()
    source_list = []
    for s in sources:
        org = db.query(Organization).filter(Organization.id == s.organization_id).first()
        notif_count = db.query(Notification).filter(
            Notification.organization_id == s.organization_id,
            Notification.is_synthetic == False,
        ).count()
        source_list.append(SourceSchema(
            id=s.id,
            name=s.name,
            base_url=s.base_url,
            recruitment_page_url=s.recruitment_page_url,
            organization_id=s.organization_id,
            organization_name=org.name if org else None,
            category=s.category.value,
            source_type=s.source_type.value,
            is_enabled=s.is_enabled,
            fetch_interval_minutes=s.fetch_interval_minutes,
            last_successful_check=s.last_successful_check,
            last_discovered_at=s.last_discovered_at,
            last_error=s.last_error,
            last_error_at=s.last_error_at,
            error_count=s.error_count,
            notifications_count=notif_count,
            parsing_strategy=s.parsing_strategy,
            robots_txt_allowed=s.robots_txt_allowed,
        ))

    return SourceStatusResponse(
        total_sources=total,
        enabled_sources=enabled,
        sources_with_errors=with_errors,
        last_discovery_run=last_run,
        sources=source_list,
    )


@router.get("/organizations", response_model=list[OrganizationSchema])
def get_organizations(db: Session = Depends(get_db)):
    return db.query(Organization).filter(Organization.is_active == True).all()


@router.get("/discovery/status", response_model=DiscoveryStatusResponse)
def discovery_status(db: Session = Depends(get_db)):
    last_log = db.query(DiscoveryLog).order_by(
        DiscoveryLog.started_at.desc()
    ).first()
    total_checked = db.query(DiscoveryLog).count()
    total_found = db.query(func.sum(DiscoveryLog.notifications_new)).scalar() or 0
    errors = db.query(DiscoveryLog).filter(
        DiscoveryLog.status == "error"
    ).order_by(DiscoveryLog.started_at.desc()).limit(10).all()

    return DiscoveryStatusResponse(
        is_running=False,
        last_run=last_log.started_at if last_log else None,
        total_sources_checked=total_checked,
        total_notifications_found=int(total_found),
        errors=[e.error_message or "Unknown error" for e in errors],
    )


@router.post("/discovery/run")
def trigger_discovery(
    request: Request,
    source_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Administrator-triggered discovery run with immediate execution."""
    verify_admin_access(request)
    engine = DiscoveryEngine(db)
    try:
        source_ids = [source_id] if source_id else None
        results = engine.run_discovery(source_ids=source_ids, force=True)
        return {
            "status": "completed",
            "message": f"Discovery run completed. Checked {len(results)} sources.",
            "sources_checked": len(results),
            "total_new": sum(r.get("new", 0) for r in results),
            "total_updated": sum(r.get("updated", 0) for r in results),
            "results": results,
        }
    finally:
        engine.close()


@router.post("/sources/{source_id}/discover")
def discover_single_source(
    source_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Test and trigger discovery for an individual source immediately."""
    verify_admin_access(request)
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    engine = DiscoveryEngine(db)
    try:
        results = engine.run_discovery(source_ids=[source_id], force=True)
        return {
            "status": "completed",
            "source_id": source_id,
            "source_name": source.name,
            "results": results[0] if results else None,
        }
    finally:
        engine.close()
