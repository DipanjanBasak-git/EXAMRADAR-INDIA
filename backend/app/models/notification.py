"""ExamRadar India - Notification & Lifecycle Models"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Enum, JSON,
    Float, ForeignKey, Date, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from app.database.session import Base


class ApplicationStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    APPLICATION_OPEN = "application_open"
    CLOSING_SOON = "closing_soon"
    CLOSED = "closed"
    CORRECTION_WINDOW = "correction_window"
    ADMIT_CARD_AVAILABLE = "admit_card_available"
    EXAM_DATE_ANNOUNCED = "exam_date_announced"
    ANSWER_KEY_RELEASED = "answer_key_released"
    RESULT_DECLARED = "result_declared"
    INTERVIEW_ANNOUNCED = "interview_announced"
    DV_ANNOUNCED = "dv_announced"
    FINAL_LIST_PUBLISHED = "final_list_published"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class VerificationStatus(str, enum.Enum):
    OFFICIAL_VERIFIED = "official_verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class EligibilityMatch(str, enum.Enum):
    LIKELY_ELIGIBLE = "likely_eligible"
    POSSIBLY_ELIGIBLE = "possibly_eligible"
    NOT_ELIGIBLE = "not_eligible"
    INSUFFICIENT_INFO = "insufficient_info"
    NOT_EVALUATED = "not_evaluated"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    # Core identification
    title = Column(String(1000), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    post_name = Column(String(500), nullable=True)
    advertisement_number = Column(String(200), nullable=True)
    notification_number = Column(String(200), nullable=True)

    # Vacancy details
    total_vacancies = Column(Integer, nullable=True)
    vacancy_details = Column(JSON, nullable=True)  # breakdown by category

    # Eligibility
    min_age = Column(Integer, nullable=True)
    max_age = Column(Integer, nullable=True)
    age_relaxation = Column(JSON, nullable=True)  # {category: years}
    age_cutoff_date = Column(Date, nullable=True)
    educational_qualification = Column(Text, nullable=True)
    qualification_details = Column(JSON, nullable=True)  # structured qual data
    experience_required = Column(Text, nullable=True)
    experience_years = Column(Integer, nullable=True)

    # Dates
    notification_date = Column(Date, nullable=True)
    application_start_date = Column(Date, nullable=True)
    application_end_date = Column(Date, nullable=True)
    correction_start_date = Column(Date, nullable=True)
    correction_end_date = Column(Date, nullable=True)
    exam_date = Column(Date, nullable=True)
    admit_card_date = Column(Date, nullable=True)
    result_date = Column(Date, nullable=True)

    # Financial
    application_fee = Column(JSON, nullable=True)  # {general: 600, sc_st: 100}
    salary_range = Column(String(500), nullable=True)
    pay_scale = Column(String(500), nullable=True)

    # Selection & location
    selection_process = Column(Text, nullable=True)
    location = Column(String(500), nullable=True)
    state = Column(String(200), nullable=True)
    employment_type = Column(String(100), nullable=True)  # permanent/contractual

    # Status
    application_status = Column(
        Enum(ApplicationStatus), default=ApplicationStatus.UPCOMING, index=True
    )
    verification_status = Column(
        Enum(VerificationStatus), default=VerificationStatus.UNVERIFIED
    )

    # Source information
    official_notification_url = Column(String(2000), nullable=True)
    official_application_url = Column(String(2000), nullable=True)
    source_url = Column(String(2000), nullable=True)
    source_domain = Column(String(500), nullable=True)
    source_publication_date = Column(Date, nullable=True)
    content_hash = Column(String(128), nullable=True)
    extraction_method = Column(String(100), nullable=True)
    verification_errors = Column(JSON, nullable=True)

    # Summary
    summary = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)

    # Discovery timestamps
    first_discovered_at = Column(DateTime, default=datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)
    last_verified_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Flags
    is_active = Column(Boolean, default=True)
    is_synthetic = Column(Boolean, default=False)  # test fixture flag

    organization = relationship("Organization", back_populates="notifications")
    lifecycle_events = relationship("LifecycleEvent", back_populates="notification")
    saved_by = relationship("SavedNotification", back_populates="notification")

    __table_args__ = (
        Index("ix_notifications_category_status", "category", "application_status"),
        Index("ix_notifications_end_date", "application_end_date"),
        Index("ix_notifications_org", "organization_id"),
    )


class LifecycleEvent(Base):
    __tablename__ = "lifecycle_events"

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    event_date = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    source_url = Column(String(2000), nullable=True)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    notification = relationship("Notification", back_populates="lifecycle_events")


class DiscoveryLog(Base):
    __tablename__ = "discovery_logs"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False)  # success, error, partial
    notifications_found = Column(Integer, default=0)
    notifications_new = Column(Integer, default=0)
    notifications_updated = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)

    source = relationship("Source", back_populates="discovery_logs")
