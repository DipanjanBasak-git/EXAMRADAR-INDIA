"""ExamRadar India - Notification API Routes"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import UserProfile, SavedNotification, ErrorReport
from app.models.notification import Notification
from app.schemas.notification import (
    NotificationListResponse, NotificationDetail, DashboardResponse
)
from app.schemas.user import ErrorReportCreate
from app.services.notifications import (
    list_notifications, get_notification_detail, get_dashboard
)

router = APIRouter(prefix="/api/v1", tags=["notifications"])


def get_current_profile(db: Session = Depends(get_db)) -> Optional[UserProfile]:
    """Get the first user profile (single-user MVP)."""
    return db.query(UserProfile).first()


@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "ExamRadar India", "version": "1.0.0"}


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    include_synthetic: bool = Query(False),
    db: Session = Depends(get_db)
):
    profile = get_current_profile(db)
    return get_dashboard(db, profile, include_synthetic=include_synthetic)


@router.get("/notifications", response_model=NotificationListResponse)
def get_notifications(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    eligibility: Optional[str] = Query(None),
    closing_within_days: Optional[int] = Query(None),
    sort_by: str = Query("newest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_synthetic: bool = Query(False),
    db: Session = Depends(get_db),
):
    profile = get_current_profile(db)
    return list_notifications(
        db=db,
        profile=profile,
        category=category,
        status=status,
        search=search,
        eligibility=eligibility,
        closing_within_days=closing_within_days,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
        include_synthetic=include_synthetic,
    )


@router.get("/notifications/new", response_model=NotificationListResponse)
def get_new_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    profile = get_current_profile(db)
    return list_notifications(
        db, profile, sort_by="newest", page=page, page_size=page_size,
    )


@router.get("/notifications/closing-soon", response_model=NotificationListResponse)
def get_closing_soon(
    days: int = Query(7, ge=1, le=30),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    profile = get_current_profile(db)
    return list_notifications(
        db, profile, closing_within_days=days,
        sort_by="deadline", page=page, page_size=page_size,
    )


@router.get("/notifications/results", response_model=NotificationListResponse)
def get_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    profile = get_current_profile(db)
    return list_notifications(
        db, profile, status="result_declared",
        sort_by="newest", page=page, page_size=page_size,
    )


@router.get("/notifications/admit-cards", response_model=NotificationListResponse)
def get_admit_cards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    profile = get_current_profile(db)
    return list_notifications(
        db, profile, status="admit_card_available",
        sort_by="newest", page=page, page_size=page_size,
    )


@router.get("/notifications/{notification_id}", response_model=NotificationDetail)
def get_notification(notification_id: int, db: Session = Depends(get_db)):
    profile = get_current_profile(db)
    detail = get_notification_detail(db, notification_id, profile)
    if not detail:
        raise HTTPException(status_code=404, detail="Notification not found")
    return detail


@router.post("/notifications/{notification_id}/report")
def report_notification(
    notification_id: int,
    report: ErrorReportCreate,
    db: Session = Depends(get_db),
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    error_report = ErrorReport(
        notification_id=notification_id,
        report_type=report.report_type,
        description=report.description,
    )
    db.add(error_report)
    db.commit()
    return {"status": "reported", "message": "Thank you for your feedback."}


@router.get("/categories")
def get_categories():
    return {
        "categories": [
            {"value": "banking", "label": "Banking"},
            {"value": "upsc", "label": "UPSC"},
            {"value": "ssc", "label": "SSC"},
            {"value": "railways", "label": "Railways"},
            {"value": "defence", "label": "Defence"},
            {"value": "central_govt", "label": "Central Government"},
            {"value": "state_govt", "label": "State Government"},
            {"value": "psu", "label": "PSUs"},
            {"value": "teaching", "label": "Teaching"},
            {"value": "police", "label": "Police & Paramilitary"},
            {"value": "research", "label": "Research & Scientific"},
            {"value": "other", "label": "Other Government"},
        ]
    }
