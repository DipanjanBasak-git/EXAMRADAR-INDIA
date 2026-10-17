"""ExamRadar India - User Profile Models"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Enum, JSON,
    Date, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database.session import Base


class ReservationCategory(str, enum.Enum):
    GENERAL = "general"
    EWS = "ews"
    OBC_NCL = "obc_ncl"
    SC = "sc"
    ST = "st"
    OTHER = "other"


class QualificationLevel(str, enum.Enum):
    TENTH = "10th"
    TWELFTH = "12th"
    DIPLOMA = "diploma"
    UNDERGRADUATE = "undergraduate"
    POSTGRADUATE = "postgraduate"
    PHD = "phd"
    PROFESSIONAL = "professional"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # Demographics (all optional)
    date_of_birth = Column(Date, nullable=True)
    state_of_residence = Column(String(200), nullable=True)
    domicile_state = Column(String(200), nullable=True)
    nationality = Column(String(100), default="Indian")
    gender = Column(String(50), nullable=True)
    reservation_category = Column(Enum(ReservationCategory), nullable=True)
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
    level = Column(Enum(QualificationLevel), nullable=False)
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
