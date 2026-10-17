"""ExamRadar India - User Profile Models"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Enum, JSON,
    Date, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database.session import Base


from sqlalchemy.types import TypeDecorator


class ReservationCategory(str, enum.Enum):
    GENERAL = "general"
    EWS = "ews"
    OBC_NCL = "obc_ncl"
    SC = "sc"
    ST = "st"
    OTHER = "other"


class SafeReservationCategory(TypeDecorator):
    """Resilient TypeDecorator that handles string variants and legacy DB values."""
    impl = String(50)
    cache_ok = True

    _TO_DB = {
        "gen": "general", "general": "general", "ur": "general",
        "ews": "ews",
        "obc": "obc_ncl", "obc_ncl": "obc_ncl", "obc-ncl": "obc_ncl",
        "sc": "sc", "st": "st", "other": "other"
    }

    _TO_ENUM = {
        "gen": ReservationCategory.GENERAL, "general": ReservationCategory.GENERAL, "ur": ReservationCategory.GENERAL,
        "ews": ReservationCategory.EWS,
        "obc": ReservationCategory.OBC_NCL, "obc_ncl": ReservationCategory.OBC_NCL, "obc-ncl": ReservationCategory.OBC_NCL,
        "sc": ReservationCategory.SC, "st": ReservationCategory.ST, "other": ReservationCategory.OTHER
    }

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, ReservationCategory):
            return value.value
        v = str(value).strip().lower()
        return self._TO_DB.get(v, "other")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        v = str(value).strip().lower()
        return self._TO_ENUM.get(v, ReservationCategory.OTHER)


class QualificationLevel(str, enum.Enum):
    TENTH = "10th"
    TWELFTH = "12th"
    DIPLOMA = "diploma"
    UNDERGRADUATE = "undergraduate"
    POSTGRADUATE = "postgraduate"
    PHD = "phd"
    PROFESSIONAL = "professional"


class SafeQualificationLevel(TypeDecorator):
    """Resilient TypeDecorator that normalizes qualification level variants."""
    impl = String(50)
    cache_ok = True

    _TO_DB = {
        "10th": "10th", "tenth": "10th", "matriculation": "10th", "matric": "10th", "ssc": "10th",
        "12th": "12th", "twelfth": "12th", "intermediate": "12th", "hsc": "12th",
        "diploma": "diploma",
        "graduate": "undergraduate", "undergraduate": "undergraduate", "bachelor": "undergraduate", "degree": "undergraduate",
        "postgraduate": "postgraduate", "post graduate": "postgraduate", "master": "postgraduate",
        "phd": "phd", "doctorate": "phd", "professional": "professional"
    }

    _TO_ENUM = {
        "10th": QualificationLevel.TENTH, "tenth": QualificationLevel.TENTH, "matriculation": QualificationLevel.TENTH, "matric": QualificationLevel.TENTH, "ssc": QualificationLevel.TENTH,
        "12th": QualificationLevel.TWELFTH, "twelfth": QualificationLevel.TWELFTH, "intermediate": QualificationLevel.TWELFTH, "hsc": QualificationLevel.TWELFTH,
        "diploma": QualificationLevel.DIPLOMA,
        "graduate": QualificationLevel.UNDERGRADUATE, "undergraduate": QualificationLevel.UNDERGRADUATE, "bachelor": QualificationLevel.UNDERGRADUATE, "degree": QualificationLevel.UNDERGRADUATE,
        "postgraduate": QualificationLevel.POSTGRADUATE, "post graduate": QualificationLevel.POSTGRADUATE, "master": QualificationLevel.POSTGRADUATE,
        "phd": QualificationLevel.PHD, "doctorate": QualificationLevel.PHD, "professional": QualificationLevel.PROFESSIONAL
    }

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, QualificationLevel):
            return value.value
        v = str(value).strip().lower()
        return self._TO_DB.get(v, "undergraduate")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        v = str(value).strip().lower()
        return self._TO_ENUM.get(v, QualificationLevel.UNDERGRADUATE)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # Demographics (all optional)
    date_of_birth = Column(Date, nullable=True)
    state_of_residence = Column(String(200), nullable=True)
    domicile_state = Column(String(200), nullable=True)
    nationality = Column(String(100), default="Indian")
    gender = Column(String(50), nullable=True)
    reservation_category = Column(SafeReservationCategory, nullable=True)
    is_pwbd = Column(Boolean, default=False)
    is_ex_serviceman = Column(Boolean, default=False)

    # Preferences
    profile_matching_enabled = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    qualifications = relationship("UserQualification", back_populates="profile",
                                   cascade="all, delete-orphan")
    career_preferences = relationship("CareerPreference", back_populates="profile",
                                       cascade="all, delete-orphan")
    saved_notifications = relationship("SavedNotification", back_populates="profile",
                                        cascade="all, delete-orphan")
    alert_preferences = relationship("AlertPreference", back_populates="profile",
                                      cascade="all, delete-orphan")


class UserQualification(Base):
    __tablename__ = "user_qualifications"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    level = Column(SafeQualificationLevel, nullable=False)
    degree_name = Column(String(300), nullable=True)
    specialization = Column(String(300), nullable=True)
    discipline = Column(String(200), nullable=True)  # engineering, science, arts, etc.
    institution = Column(String(500), nullable=True)
    graduation_status = Column(String(50), default="completed")  # completed/pursuing
    graduation_year = Column(Integer, nullable=True)
    expected_graduation_year = Column(Integer, nullable=True)
    percentage = Column(String(20), nullable=True)
    cgpa = Column(String(20), nullable=True)
    is_highest = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("UserProfile", back_populates="qualifications")


class CareerPreference(Base):
    __tablename__ = "career_preferences"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    preference_type = Column(String(100), nullable=False)  # category / level
    preference_value = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("UserProfile", back_populates="career_preferences")


class SavedNotification(Base):
    __tablename__ = "saved_notifications"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=False)
    is_applied = Column(Boolean, default=False)
    is_hidden = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    saved_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("UserProfile", back_populates="saved_notifications")
    notification = relationship("Notification", back_populates="saved_by")


class AlertPreference(Base):
    __tablename__ = "alert_preferences"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    alert_type = Column(String(100), nullable=False)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("UserProfile", back_populates="alert_preferences")


class ErrorReport(Base):
    __tablename__ = "error_reports"

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=False)
    report_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
