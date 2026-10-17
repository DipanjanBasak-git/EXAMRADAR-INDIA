"""ExamRadar India - Notification Service

Handles CRUD, filtering, pagination, status calculation, and dashboard aggregation.
"""

from datetime import date, datetime, timedelta, time
from typing import Optional, Union
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_, desc, asc

from app.models.notification import (
    Notification, ApplicationStatus, VerificationStatus, LifecycleEvent
)
from app.models.source import Organization
from app.models.user import UserProfile, SavedNotification
from app.schemas.notification import (
    NotificationCard, NotificationDetail, NotificationListResponse, DashboardResponse
)
from app.services.eligibility import evaluate_eligibility, EligibilityMatch

# Authoritative timezone for Indian government examinations
IST = ZoneInfo("Asia/Kolkata")


def get_current_ist_datetime() -> datetime:
    """Get the current datetime in Asia/Kolkata (IST) timezone."""
    return datetime.now(IST)


def get_current_ist_date() -> date:
    """Get the current calendar date in Asia/Kolkata (IST) timezone."""
    return datetime.now(IST).date()


def parse_deadline_to_ist(deadline_val: Union[date, datetime, str, None]) -> Optional[datetime]:
    """
    Convert a deadline (date, datetime, or ISO string) to an aware Asia/Kolkata datetime.
    Date-only deadlines default to 23:59:59 IST on that closing date.
    """
    if not deadline_val:
        return None
    if isinstance(deadline_val, str):
        try:
            deadline_val = datetime.fromisoformat(deadline_val)
        except Exception:
            try:
                deadline_val = date.fromisoformat(deadline_val)
            except Exception:
                return None
    if isinstance(deadline_val, datetime):
        if deadline_val.tzinfo is None:
            return deadline_val.replace(tzinfo=IST)
        return deadline_val.astimezone(IST)
    if isinstance(deadline_val, date):
        return datetime.combine(deadline_val, time(23, 59, 59), tzinfo=IST)
    return None


def get_effective_deadline(notification: Notification) -> tuple[Optional[date], bool]:
    """
    Determine the authoritative closing date, accounting for Corrigenda/Extensions.
    Returns (effective_end_date, is_extended).
    """
    effective_end = notification.application_end_date
    is_extended = False

    if hasattr(notification, "lifecycle_events") and notification.lifecycle_events:
        for ev in notification.lifecycle_events:
            ev_type = (ev.event_type or "").lower()
            if any(k in ev_type for k in ["deadline_extended", "extension", "corrigendum", "last_date_extended"]):
                if ev.event_date:
                    ev_date = ev.event_date.date() if isinstance(ev.event_date, datetime) else ev.event_date
                    if effective_end is None or ev_date > effective_end:
                        effective_end = ev_date
                        is_extended = True

    return effective_end, is_extended


def calculate_deadline_metrics(notification: Notification) -> dict:
    """
    Calculate precise deadline metrics against Asia/Kolkata time.
    Handles date-only deadlines (open through 23:59:59 IST), timezone conversions,
    and extensions to application deadlines.
    """
    today_ist = get_current_ist_date()
    now_ist = get_current_ist_datetime()
    effective_end, is_extended = get_effective_deadline(notification)

    if not effective_end:
        return {
            "effective_end_date": None,
            "is_extended": False,
            "is_expired": False,
            "days_remaining": None,
            "status": notification.application_status or ApplicationStatus.UPCOMING,
        }

    deadline_dt = parse_deadline_to_ist(effective_end)
    is_expired = now_ist > deadline_dt if deadline_dt else (effective_end < today_ist)
    days_remaining = (effective_end - today_ist).days if not is_expired else 0

    if is_expired:
        status = ApplicationStatus.CLOSED
    elif 0 <= days_remaining <= 3:
        status = ApplicationStatus.CLOSING_SOON
    elif notification.application_start_date and notification.application_start_date <= today_ist:
        status = ApplicationStatus.APPLICATION_OPEN
    elif notification.application_start_date and notification.application_start_date > today_ist:
        status = ApplicationStatus.UPCOMING
    else:
        status = ApplicationStatus.APPLICATION_OPEN

    return {
        "effective_end_date": effective_end,
        "is_extended": is_extended,
        "is_expired": is_expired,
        "days_remaining": days_remaining,
        "status": status,
    }


def calculate_application_status(notification: Notification) -> ApplicationStatus:
    """Determine current application status using Asia/Kolkata timezone and effective deadlines."""
    today_ist = get_current_ist_date()

    if notification.application_status in (
        ApplicationStatus.CANCELLED, ApplicationStatus.SUPERSEDED
    ):
        return notification.application_status

    if notification.result_date and notification.result_date <= today_ist:
        return ApplicationStatus.RESULT_DECLARED

    if notification.admit_card_date and notification.admit_card_date <= today_ist:
        if not notification.result_date or notification.result_date > today_ist:
            return ApplicationStatus.ADMIT_CARD_AVAILABLE

    if notification.exam_date and notification.exam_date <= today_ist:
        return ApplicationStatus.EXAM_DATE_ANNOUNCED

    metrics = calculate_deadline_metrics(notification)
    return metrics["status"]


def notification_to_card(
    notification: Notification,
    profile: Optional[UserProfile] = None,
    saved_ids: set = None,
    applied_ids: set = None,
) -> NotificationCard:
    """Convert a Notification ORM object to a NotificationCard schema."""
    org = notification.organization
    saved_ids = saved_ids or set()
    applied_ids = applied_ids or set()

    eligibility_match = None
    eligibility_explanation = None
    if profile and profile.profile_matching_enabled:
        result = evaluate_eligibility(notification, profile)
        eligibility_match = result.match.value
        eligibility_explanation = result.explanation

    return NotificationCard(
        id=notification.id,
        title=notification.title,
        organization_name=org.name if org else "Unknown",
        organization_short_name=org.short_name if org else None,
        category=notification.category,
        post_name=notification.post_name,
        advertisement_number=notification.advertisement_number,
        total_vacancies=notification.total_vacancies,
        min_age=notification.min_age,
        max_age=notification.max_age,
        educational_qualification=notification.educational_qualification,
        application_start_date=notification.application_start_date,
        application_end_date=notification.application_end_date,
        application_fee=notification.application_fee,
        salary_range=notification.salary_range,
        location=notification.location,
        application_status=calculate_application_status(notification).value,
        verification_status=notification.verification_status.value
            if notification.verification_status else VerificationStatus.UNVERIFIED.value,
        official_notification_url=notification.official_notification_url,
        official_application_url=notification.official_application_url,
        first_discovered_at=notification.first_discovered_at,
        last_verified_at=notification.last_verified_at,
        is_synthetic=notification.is_synthetic,
        eligibility_match=eligibility_match,
        eligibility_explanation=eligibility_explanation,
        is_saved=notification.id in saved_ids,
        is_applied=notification.id in applied_ids,
    )


def get_user_saved_applied_ids(db: Session, profile_id: int):
    """Get sets of saved and applied notification IDs for a user."""
    saved_rows = db.query(SavedNotification).filter(
        SavedNotification.profile_id == profile_id,
        SavedNotification.is_hidden == False,
    ).all()
    saved_ids = {s.notification_id for s in saved_rows if not s.is_applied}
    applied_ids = {s.notification_id for s in saved_rows if s.is_applied}
    return saved_ids, applied_ids


def list_notifications(
    db: Session,
    profile: Optional[UserProfile] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    eligibility: Optional[str] = None,
    closing_within_days: Optional[int] = None,
    sort_by: str = "newest",
    page: int = 1,
    page_size: int = 20,
    include_synthetic: bool = False,
) -> NotificationListResponse:
    """List notifications with filtering and pagination."""
    query = db.query(Notification).options(
        joinedload(Notification.organization)
    ).filter(Notification.is_active == True)

    if not include_synthetic:
        query = query.filter(Notification.is_synthetic == False)

    if category:
        query = query.filter(Notification.category == category)

    if status:
        query = query.filter(Notification.application_status == status)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Notification.title.ilike(search_term),
                Notification.post_name.ilike(search_term),
                Notification.advertisement_number.ilike(search_term),
            )
        )

    if closing_within_days:
        today = get_current_ist_date()
        deadline = today + timedelta(days=closing_within_days)
        query = query.filter(
            Notification.application_end_date.isnot(None),
            Notification.application_end_date >= today,
            Notification.application_end_date <= deadline,
        )

    # Sorting
    if sort_by == "deadline":
        query = query.order_by(asc(Notification.application_end_date))
    elif sort_by == "start_date":
        query = query.order_by(desc(Notification.application_start_date))
    elif sort_by == "organization":
        query = query.join(Organization).order_by(asc(Organization.name))
    else:  # newest
        query = query.order_by(desc(Notification.first_discovered_at))

    total = query.count()
    notifications = query.offset((page - 1) * page_size).limit(page_size).all()

    saved_ids, applied_ids = set(), set()
    if profile:
        saved_ids, applied_ids = get_user_saved_applied_ids(db, profile.id)

    cards = [
        notification_to_card(n, profile, saved_ids, applied_ids)
        for n in notifications
    ]

    # Post-filter by eligibility if requested
    if eligibility and profile:
        cards = [c for c in cards if c.eligibility_match == eligibility]
        total = len(cards)

    return NotificationListResponse(
        items=cards,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


def get_notification_detail(
    db: Session, notification_id: int, profile: Optional[UserProfile] = None
) -> Optional[NotificationDetail]:
    """Get full notification detail."""
    notification = db.query(Notification).options(
        joinedload(Notification.organization),
        joinedload(Notification.lifecycle_events),
    ).filter(Notification.id == notification_id).first()

    if not notification:
        return None

    org = notification.organization
    saved_ids, applied_ids = set(), set()
    if profile:
        saved_ids, applied_ids = get_user_saved_applied_ids(db, profile.id)

    eligibility_match = None
    eligibility_explanation = None
    if profile and profile.profile_matching_enabled:
        result = evaluate_eligibility(notification, profile)
        eligibility_match = result.match.value
        eligibility_explanation = result.explanation

    events = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "event_date": e.event_date.isoformat() if e.event_date else None,
            "description": e.description,
            "source_url": e.source_url,
            "verified": e.verified,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in notification.lifecycle_events
    ]

    return NotificationDetail(
        id=notification.id,
        title=notification.title,
        organization_id=notification.organization_id,
        organization_name=org.name if org else "Unknown",
        organization_short_name=org.short_name if org else None,
        category=notification.category,
        post_name=notification.post_name,
        advertisement_number=notification.advertisement_number,
        notification_number=notification.notification_number,
        total_vacancies=notification.total_vacancies,
        vacancy_details=notification.vacancy_details,
        min_age=notification.min_age,
        max_age=notification.max_age,
        age_relaxation=notification.age_relaxation,
        age_cutoff_date=notification.age_cutoff_date,
        educational_qualification=notification.educational_qualification,
        qualification_details=notification.qualification_details,
        experience_required=notification.experience_required,
        experience_years=notification.experience_years,
        notification_date=notification.notification_date,
        application_start_date=notification.application_start_date,
        application_end_date=notification.application_end_date,
        correction_start_date=notification.correction_start_date,
        correction_end_date=notification.correction_end_date,
        exam_date=notification.exam_date,
        admit_card_date=notification.admit_card_date,
        result_date=notification.result_date,
        application_fee=notification.application_fee,
        salary_range=notification.salary_range,
        pay_scale=notification.pay_scale,
        selection_process=notification.selection_process,
        location=notification.location,
        state=notification.state,
        employment_type=notification.employment_type,
        application_status=calculate_application_status(notification).value,
        verification_status=notification.verification_status.value
            if notification.verification_status else VerificationStatus.UNVERIFIED.value,
        official_notification_url=notification.official_notification_url,
        official_application_url=notification.official_application_url,
        source_url=notification.source_url,
        source_domain=notification.source_domain,
        source_publication_date=notification.source_publication_date,
        content_hash=notification.content_hash,
        extraction_method=notification.extraction_method,
        verification_errors=notification.verification_errors,
        summary=notification.summary,
        first_discovered_at=notification.first_discovered_at,
        last_checked_at=notification.last_checked_at,
        last_verified_at=notification.last_verified_at,
        updated_at=notification.updated_at,
        is_active=notification.is_active,
        is_synthetic=notification.is_synthetic,
        lifecycle_events=events,
        eligibility_match=eligibility_match,
        eligibility_explanation=eligibility_explanation,
        is_saved=notification.id in saved_ids,
        is_applied=notification.id in applied_ids,
    )


def get_dashboard(
    db: Session,
    profile: Optional[UserProfile] = None,
    include_synthetic: bool = False,
) -> DashboardResponse:
    """Aggregate dashboard data using Asia/Kolkata timezone."""
    today = get_current_ist_date()
    seven_days = today + timedelta(days=7)
    yesterday = datetime.utcnow() - timedelta(days=1)

    base = db.query(Notification).options(
        joinedload(Notification.organization)
    ).filter(Notification.is_active == True)

    if not include_synthetic:
        base = base.filter(Notification.is_synthetic == False)

    # Counts
    open_q = base.filter(
        or_(
            Notification.application_start_date.is_(None),
            Notification.application_start_date <= today,
        ),
        or_(
            Notification.application_end_date.is_(None),
            Notification.application_end_date >= today,
        ),
    )
    total_open = open_q.count()

    newly_discovered = base.filter(
        Notification.first_discovered_at >= yesterday
    ).count()

    closing_soon_q = base.filter(
        Notification.application_end_date.isnot(None),
        Notification.application_end_date >= today,
        Notification.application_end_date <= seven_days,
    )
    closing_soon_count = closing_soon_q.count()

    # Recent
    recent = base.order_by(
        desc(Notification.first_discovered_at)
    ).limit(10).all()

    closing_soon_list = closing_soon_q.order_by(
        asc(Notification.application_end_date)
    ).limit(10).all()

    saved_ids, applied_ids = set(), set()
    if profile:
        saved_ids, applied_ids = get_user_saved_applied_ids(db, profile.id)

    recent_cards = [
        notification_to_card(n, profile, saved_ids, applied_ids) for n in recent
    ]
    closing_cards = [
        notification_to_card(n, profile, saved_ids, applied_ids) for n in closing_soon_list
    ]

    # Recommended (eligible matches)
    matching_count = 0
    recommended_cards = []
    if profile and profile.profile_matching_enabled:
        open_notifications = open_q.limit(50).all()
        for n in open_notifications:
            result = evaluate_eligibility(n, profile)
            if result.match in (EligibilityMatch.LIKELY_ELIGIBLE, EligibilityMatch.POSSIBLY_ELIGIBLE):
                matching_count += 1
                if len(recommended_cards) < 10:
                    card = notification_to_card(n, profile, saved_ids, applied_ids)
                    recommended_cards.append(card)

    # Last updated
    last_notif = db.query(func.max(Notification.first_discovered_at)).scalar()

    return DashboardResponse(
        total_open=total_open,
        newly_discovered=newly_discovered,
        matching_profile=matching_count,
        closing_soon=closing_soon_count,
        last_updated=last_notif,
        recent_notifications=recent_cards,
        closing_soon_notifications=closing_cards,
        recommended_notifications=recommended_cards,
    )
