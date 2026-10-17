"""ExamRadar India - Pydantic Schemas for Notifications"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class NotificationBase(BaseModel):
    title: str
    category: str
    post_name: Optional[str] = None
    advertisement_number: Optional[str] = None
    notification_number: Optional[str] = None
    total_vacancies: Optional[int] = None
    vacancy_details: Optional[dict] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    age_relaxation: Optional[dict] = None
    age_cutoff_date: Optional[date] = None
    educational_qualification: Optional[str] = None
    qualification_details: Optional[dict] = None
    experience_required: Optional[str] = None
    experience_years: Optional[int] = None
    notification_date: Optional[date] = None
    application_start_date: Optional[date] = None
    application_end_date: Optional[date] = None
    correction_start_date: Optional[date] = None
    correction_end_date: Optional[date] = None
    exam_date: Optional[date] = None
    admit_card_date: Optional[date] = None
    result_date: Optional[date] = None
    application_fee: Optional[dict] = None
    salary_range: Optional[str] = None
    pay_scale: Optional[str] = None
    selection_process: Optional[str] = None
    location: Optional[str] = None
    state: Optional[str] = None
    employment_type: Optional[str] = None
    official_notification_url: Optional[str] = None
    official_application_url: Optional[str] = None
    summary: Optional[str] = None


class NotificationCreate(NotificationBase):
    organization_id: int
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    extraction_method: Optional[str] = None
    raw_text: Optional[str] = None


class NotificationCard(BaseModel):
    """Compact representation for listing."""
    id: int
    title: str
    organization_name: str
    organization_short_name: Optional[str] = None
    category: str
    post_name: Optional[str] = None
    advertisement_number: Optional[str] = None
    total_vacancies: Optional[int] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    educational_qualification: Optional[str] = None
    application_start_date: Optional[date] = None
    application_end_date: Optional[date] = None
    application_fee: Optional[dict] = None
    salary_range: Optional[str] = None
    location: Optional[str] = None
    application_status: str
    verification_status: str
    official_notification_url: Optional[str] = None
    official_application_url: Optional[str] = None
    first_discovered_at: datetime
    last_verified_at: Optional[datetime] = None
    is_synthetic: bool = False

    # Eligibility match (populated per-user)
    eligibility_match: Optional[str] = None
    eligibility_explanation: Optional[str] = None

    # User-specific
    is_saved: bool = False
    is_applied: bool = False

    model_config = ConfigDict(from_attributes=True)


class NotificationDetail(NotificationBase):
    """Full notification detail."""
    id: int
    organization_id: int
    organization_name: str
    organization_short_name: Optional[str] = None
    application_status: str
    verification_status: str
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    source_publication_date: Optional[date] = None
    content_hash: Optional[str] = None
    extraction_method: Optional[str] = None
    verification_errors: Optional[dict] = None
    first_discovered_at: datetime
    last_checked_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    updated_at: datetime
    is_active: bool
    is_synthetic: bool = False
    lifecycle_events: list = []

    eligibility_match: Optional[str] = None
    eligibility_explanation: Optional[str] = None
    is_saved: bool = False
    is_applied: bool = False

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: list[NotificationCard]
    total: int
    page: int
    page_size: int
    has_more: bool


class DashboardResponse(BaseModel):
    total_open: int = 0
    newly_discovered: int = 0
    matching_profile: int = 0
    closing_soon: int = 0
    last_updated: Optional[datetime] = None
    recent_notifications: list[NotificationCard] = []
    closing_soon_notifications: list[NotificationCard] = []
    recommended_notifications: list[NotificationCard] = []


class LifecycleEventSchema(BaseModel):
    id: int
    notification_id: int
    event_type: str
    event_date: Optional[datetime] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    verified: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
