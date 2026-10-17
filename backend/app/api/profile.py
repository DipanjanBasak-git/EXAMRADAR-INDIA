"""ExamRadar India - Profile & Saved Items API Routes"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import (
    UserProfile, UserQualification, CareerPreference,
    SavedNotification, AlertPreference
)
from app.models.notification import Notification
from app.schemas.user import (
    ProfileCreate, ProfileResponse, QualificationSchema,
    CareerPreferenceSchema, AlertPreferenceSchema, SavedNotificationSchema
)

router = APIRouter(prefix="/api/v1", tags=["profile"])


def get_or_create_profile(db: Session) -> UserProfile:
    """Get the first profile or create one (single-user MVP)."""
    profile = db.query(UserProfile).first()
    if not profile:
        profile = UserProfile()
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("/profile", response_model=ProfileResponse)
def get_profile(db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    return profile


@router.put("/profile", response_model=ProfileResponse)
def update_profile(data: ProfileCreate, db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)

    # Update demographics
    profile.date_of_birth = data.date_of_birth
    profile.state_of_residence = data.state_of_residence
    profile.domicile_state = data.domicile_state
    profile.nationality = data.nationality
    profile.gender = data.gender
    profile.reservation_category = data.reservation_category
    profile.is_pwbd = data.is_pwbd
    profile.is_ex_serviceman = data.is_ex_serviceman
    profile.profile_matching_enabled = data.profile_matching_enabled

    # Update qualifications
    db.query(UserQualification).filter(
        UserQualification.profile_id == profile.id
    ).delete()
    for q in data.qualifications:
        qual = UserQualification(
            profile_id=profile.id,
            level=q.level,
            degree_name=q.degree_name,
            specialization=q.specialization,
            discipline=q.discipline,
            institution=q.institution,
            graduation_status=q.graduation_status,
            graduation_year=q.graduation_year,
            expected_graduation_year=q.expected_graduation_year,
            percentage=q.percentage,
            cgpa=q.cgpa,
            is_highest=q.is_highest,
        )
        db.add(qual)

    # Update career preferences
    db.query(CareerPreference).filter(
        CareerPreference.profile_id == profile.id
    ).delete()
    for p in data.career_preferences:
        pref = CareerPreference(
            profile_id=profile.id,
            preference_type=p.preference_type,
            preference_value=p.preference_value,
            is_active=p.is_active,
        )
        db.add(pref)

    db.commit()
    db.refresh(profile)
    return profile


@router.post("/profile/match")
def match_profile(db: Session = Depends(get_db)):
    """Trigger re-evaluation of eligibility matches for all notifications."""
    profile = db.query(UserProfile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile configured")

    # Eligibility is computed on-the-fly, so this is essentially a no-op
    # that confirms the profile exists and matching is enabled.
    return {
        "status": "ok",
        "matching_enabled": profile.profile_matching_enabled,
        "message": "Eligibility matching is computed dynamically for each notification."
    }


@router.delete("/profile")
def delete_profile(db: Session = Depends(get_db)):
    profile = db.query(UserProfile).first()
    if profile:
        db.delete(profile)
        db.commit()
    return {"status": "deleted"}


# --- Saved Notifications ---

@router.get("/saved", response_model=list[SavedNotificationSchema])
def get_saved(db: Session = Depends(get_db)):
    from app.services.notifications import notification_to_card
    profile = db.query(UserProfile).first()
    if not profile:
        return []
    saved_rows = db.query(SavedNotification).filter(
        SavedNotification.profile_id == profile.id,
        SavedNotification.is_hidden == False,
    ).all()
    results = []
    for s in saved_rows:
        notif_card = notification_to_card(s.notification, profile) if s.notification else None
        schema = SavedNotificationSchema(
            id=s.id,
            notification_id=s.notification_id,
            is_applied=s.is_applied,
            is_hidden=s.is_hidden,
            notes=s.notes,
            saved_at=s.saved_at,
            notification=notif_card,
        )
        results.append(schema)
    return results


@router.post("/saved/{notification_id}")
def save_notification(notification_id: int, db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    existing = db.query(SavedNotification).filter(
        SavedNotification.profile_id == profile.id,
        SavedNotification.notification_id == notification_id,
    ).first()
    if existing:
        return {"status": "already_saved"}

    saved = SavedNotification(
        profile_id=profile.id,
        notification_id=notification_id,
    )
    db.add(saved)
    db.commit()
    return {"status": "saved"}


@router.delete("/saved/{notification_id}")
def unsave_notification(notification_id: int, db: Session = Depends(get_db)):
    profile = db.query(UserProfile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile")
    saved = db.query(SavedNotification).filter(
        SavedNotification.profile_id == profile.id,
        SavedNotification.notification_id == notification_id,
    ).first()
    if saved:
        db.delete(saved)
        db.commit()
    return {"status": "removed"}


@router.put("/saved/{notification_id}/applied")
def mark_applied(notification_id: int, db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    saved = db.query(SavedNotification).filter(
        SavedNotification.profile_id == profile.id,
        SavedNotification.notification_id == notification_id,
    ).first()
    if not saved:
        # Auto-save then mark applied
        saved = SavedNotification(
            profile_id=profile.id,
            notification_id=notification_id,
            is_applied=True,
        )
        db.add(saved)
    else:
        saved.is_applied = True
    db.commit()
    return {"status": "marked_applied"}


# --- Alert Preferences ---

@router.get("/alerts", response_model=list[AlertPreferenceSchema])
def get_alerts(db: Session = Depends(get_db)):
    profile = db.query(UserProfile).first()
    if not profile:
        return []
    return db.query(AlertPreference).filter(
        AlertPreference.profile_id == profile.id
    ).all()


@router.put("/alerts/preferences")
def update_alerts(preferences: list[AlertPreferenceSchema], db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    db.query(AlertPreference).filter(
        AlertPreference.profile_id == profile.id
    ).delete()
    for p in preferences:
        alert = AlertPreference(
            profile_id=profile.id,
            alert_type=p.alert_type,
            is_enabled=p.is_enabled,
        )
        db.add(alert)
    db.commit()
    return {"status": "updated"}
