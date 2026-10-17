"""ExamRadar India - Pydantic Schemas for User Profile"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class QualificationSchema(BaseModel):
    id: Optional[int] = None
    level: str
    degree_name: Optional[str] = None
    specialization: Optional[str] = None
    discipline: Optional[str] = None
    institution: Optional[str] = None
    graduation_status: str = "completed"
    graduation_year: Optional[int] = None
    expected_graduation_year: Optional[int] = None
    percentage: Optional[str] = None
    cgpa: Optional[str] = None
    is_highest: bool = False

    model_config = ConfigDict(from_attributes=True)


class CareerPreferenceSchema(BaseModel):
    id: Optional[int] = None
    preference_type: str
    preference_value: str
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class AlertPreferenceSchema(BaseModel):
    id: Optional[int] = None
    alert_type: str
    is_enabled: bool = True

    model_config = ConfigDict(from_attributes=True)


class ProfileCreate(BaseModel):
    date_of_birth: Optional[date] = None
    state_of_residence: Optional[str] = None
    domicile_state: Optional[str] = None
    nationality: str = "Indian"
    gender: Optional[str] = None
    reservation_category: Optional[str] = None
    is_pwbd: bool = False
    is_ex_serviceman: bool = False
    profile_matching_enabled: bool = True
    qualifications: list[QualificationSchema] = []
    career_preferences: list[CareerPreferenceSchema] = []


class ProfileResponse(BaseModel):
    id: int
    date_of_birth: Optional[date] = None
    state_of_residence: Optional[str] = None
    domicile_state: Optional[str] = None
    nationality: str = "Indian"
    gender: Optional[str] = None
    reservation_category: Optional[str] = None
    is_pwbd: bool = False
    is_ex_serviceman: bool = False
    profile_matching_enabled: bool = True
    qualifications: list[QualificationSchema] = []
    career_preferences: list[CareerPreferenceSchema] = []
    alert_preferences: list[AlertPreferenceSchema] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


from app.schemas.notification import NotificationCard


class SavedNotificationSchema(BaseModel):
    id: int
    notification_id: int
    is_applied: bool = False
    is_hidden: bool = False
    notes: Optional[str] = None
    saved_at: datetime
    notification: Optional[NotificationCard] = None

    model_config = ConfigDict(from_attributes=True)


class ErrorReportCreate(BaseModel):
    report_type: str
    description: Optional[str] = None
