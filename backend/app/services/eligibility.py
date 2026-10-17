"""ExamRadar India - Eligibility Matching Engine

Compares official eligibility criteria against the user's saved profile.
Returns one of: likely_eligible, possibly_eligible, not_eligible, insufficient_info.
"""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo
from app.models.notification import Notification, EligibilityMatch
from app.models.user import UserProfile, UserQualification, ReservationCategory, QualificationLevel

IST = ZoneInfo("Asia/Kolkata")


def get_current_ist_date() -> date:
    """Current calendar date in Asia/Kolkata timezone."""
    return datetime.now(IST).date()


# Qualification hierarchy for comparison
QUALIFICATION_HIERARCHY = {
    QualificationLevel.TENTH: 1,
    QualificationLevel.TWELFTH: 2,
    QualificationLevel.DIPLOMA: 2,
    QualificationLevel.UNDERGRADUATE: 3,
    QualificationLevel.POSTGRADUATE: 4,
    QualificationLevel.PHD: 5,
    QualificationLevel.PROFESSIONAL: 4,
}

# Standard age relaxation rules (years)
STANDARD_AGE_RELAXATION = {
    ReservationCategory.GENERAL: 0,
    ReservationCategory.EWS: 0,
    ReservationCategory.OBC_NCL: 3,
    ReservationCategory.SC: 5,
    ReservationCategory.ST: 5,
    ReservationCategory.OTHER: 0,
}

PWBD_ADDITIONAL_RELAXATION = 10
EX_SERVICEMAN_ADDITIONAL_RELAXATION = 5

# Keyword-to-qualification level mapping
QUAL_KEYWORDS = {
    "10th": QualificationLevel.TENTH,
    "tenth": QualificationLevel.TENTH,
    "matriculation": QualificationLevel.TENTH,
    "matric": QualificationLevel.TENTH,
    "ssc": QualificationLevel.TENTH,
    "12th": QualificationLevel.TWELFTH,
    "twelfth": QualificationLevel.TWELFTH,
    "intermediate": QualificationLevel.TWELFTH,
    "hsc": QualificationLevel.TWELFTH,
    "higher secondary": QualificationLevel.TWELFTH,
    "diploma": QualificationLevel.DIPLOMA,
    "graduate": QualificationLevel.UNDERGRADUATE,
    "graduation": QualificationLevel.UNDERGRADUATE,
    "degree": QualificationLevel.UNDERGRADUATE,
    "b.tech": QualificationLevel.UNDERGRADUATE,
    "b.e.": QualificationLevel.UNDERGRADUATE,
    "b.sc": QualificationLevel.UNDERGRADUATE,
    "b.a.": QualificationLevel.UNDERGRADUATE,
    "b.com": QualificationLevel.UNDERGRADUATE,
    "bachelor": QualificationLevel.UNDERGRADUATE,
    "post graduate": QualificationLevel.POSTGRADUATE,
    "postgraduate": QualificationLevel.POSTGRADUATE,
    "master": QualificationLevel.POSTGRADUATE,
    "m.tech": QualificationLevel.POSTGRADUATE,
    "m.sc": QualificationLevel.POSTGRADUATE,
    "m.a.": QualificationLevel.POSTGRADUATE,
    "mba": QualificationLevel.POSTGRADUATE,
    "m.com": QualificationLevel.POSTGRADUATE,
    "phd": QualificationLevel.PHD,
    "doctorate": QualificationLevel.PHD,
    "ca": QualificationLevel.PROFESSIONAL,
    "cs": QualificationLevel.PROFESSIONAL,
    "llb": QualificationLevel.PROFESSIONAL,
    "mbbs": QualificationLevel.PROFESSIONAL,
}


class MatchResult:
    """Result of an eligibility evaluation."""

    def __init__(
        self,
        match: EligibilityMatch = EligibilityMatch.NOT_EVALUATED,
        explanation: str = "",
        checks: list[dict] = None,
    ):
        self.match = match
        self.explanation = explanation
        self.checks = checks or []

    def to_dict(self):
        return {
            "match": self.match.value,
            "explanation": self.explanation,
            "checks": self.checks,
        }


def calculate_age(dob: date, cutoff: date) -> int:
    """Calculate age in completed years as of a cutoff date."""
    age = cutoff.year - dob.year
    if (cutoff.month, cutoff.day) < (dob.month, dob.day):
        age -= 1
    return age


def get_max_age_with_relaxation(
    max_age: int,
    notification: Notification,
    profile: UserProfile,
) -> int:
    """Apply category-based age relaxation to the stated maximum age."""
    relaxed_max = max_age

    # Check if notification provides its own relaxation rules
    if notification.age_relaxation and profile.reservation_category:
        cat_key = profile.reservation_category.value
        if cat_key in notification.age_relaxation:
            try:
                relaxed_max = max_age + int(notification.age_relaxation[cat_key])
            except (ValueError, TypeError):
                pass
    elif profile.reservation_category:
        # Use standard relaxation
        standard = STANDARD_AGE_RELAXATION.get(
            profile.reservation_category, 0
        )
        relaxed_max = max_age + standard

    if profile.is_pwbd:
        relaxed_max += PWBD_ADDITIONAL_RELAXATION

    if profile.is_ex_serviceman:
        relaxed_max += EX_SERVICEMAN_ADDITIONAL_RELAXATION

    return relaxed_max


def infer_required_qualification(text: str) -> Optional[QualificationLevel]:
    """Infer the minimum required qualification from advertisement text."""
    if not text:
        return None
    text_lower = text.lower()
    best_match = None
    best_level = 0
    for keyword, level in QUAL_KEYWORDS.items():
        if keyword in text_lower:
            rank = QUALIFICATION_HIERARCHY.get(level, 0)
            if rank > best_level:
                best_level = rank
                best_match = level
    return best_match


def get_user_highest_qualification(
    qualifications: list[UserQualification],
) -> Optional[UserQualification]:
    """Get the user's highest completed qualification."""
    completed = [
        q for q in qualifications if q.graduation_status == "completed"
    ]
    if not completed:
        return None
    return max(
        completed,
        key=lambda q: QUALIFICATION_HIERARCHY.get(q.level, 0),
    )


def evaluate_eligibility(
    notification: Notification, profile: UserProfile
) -> MatchResult:
    """
    Evaluate eligibility of a user profile against a notification's criteria.

    Returns a MatchResult with one of:
    - LIKELY_ELIGIBLE: All checked criteria appear satisfied
    - POSSIBLY_ELIGIBLE: Some criteria uncertain
    - NOT_ELIGIBLE: A mandatory criterion is not satisfied
    - INSUFFICIENT_INFO: Not enough information to assess
    """
    checks = []
    uncertain_reasons = []
    fail_reasons = []
    pass_reasons = []
    info_missing = []

    # --- Age Check ---
    if notification.max_age and profile.date_of_birth:
        cutoff = notification.age_cutoff_date or (
            notification.application_end_date or get_current_ist_date()
        )
        user_age = calculate_age(profile.date_of_birth, cutoff)
        relaxed_max = get_max_age_with_relaxation(
            notification.max_age, notification, profile
        )

        min_age = notification.min_age or 18

        if min_age <= user_age <= relaxed_max:
            msg = (
                f"Age {user_age} is within the permitted range "
                f"({min_age}-{relaxed_max} years)."
            )
            pass_reasons.append(msg)
            checks.append({"check": "age", "result": "pass", "detail": msg})
        elif user_age > relaxed_max:
            msg = (
                f"Age {user_age} exceeds the maximum age limit of "
                f"{relaxed_max} years (including applicable relaxation)."
            )
            fail_reasons.append(msg)
            checks.append({"check": "age", "result": "fail", "detail": msg})
        elif user_age < min_age:
            msg = (
                f"Age {user_age} is below the minimum age of {min_age} years."
            )
            fail_reasons.append(msg)
            checks.append({"check": "age", "result": "fail", "detail": msg})
    elif notification.max_age and not profile.date_of_birth:
        info_missing.append("Date of birth not provided; age check skipped.")
        checks.append({
            "check": "age", "result": "missing",
            "detail": "Date of birth not set in profile."
        })
    elif not notification.max_age:
        info_missing.append("Age limit not specified in the advertisement.")
        checks.append({
            "check": "age", "result": "not_specified",
            "detail": "No age limit found in the notification."
        })

    # --- Educational Qualification Check ---
    user_highest = get_user_highest_qualification(profile.qualifications)
    required_level = None

    if notification.qualification_details and "min_level" in notification.qualification_details:
        try:
            required_level = QualificationLevel(notification.qualification_details["min_level"])
        except ValueError:
            pass

    if not required_level and notification.educational_qualification:
        required_level = infer_required_qualification(notification.educational_qualification)

    if required_level and user_highest:
        user_rank = QUALIFICATION_HIERARCHY.get(user_highest.level, 0)
        required_rank = QUALIFICATION_HIERARCHY.get(required_level, 0)

        if user_rank >= required_rank:
            msg = (
                f"Your qualification ({user_highest.degree_name or user_highest.level.value}) "
                f"meets or exceeds the requirement ({required_level.value})."
            )
            pass_reasons.append(msg)
            checks.append({"check": "qualification", "result": "pass", "detail": msg})
        else:
            msg = (
                f"Your highest qualification ({user_highest.degree_name or user_highest.level.value}) "
                f"may not meet the required level ({required_level.value})."
            )
            fail_reasons.append(msg)
            checks.append({"check": "qualification", "result": "fail", "detail": msg})
    elif required_level and not user_highest:
        info_missing.append("No completed qualifications in your profile.")
        checks.append({
            "check": "qualification", "result": "missing",
            "detail": "No completed qualifications found in profile."
        })
    elif not required_level:
        if notification.educational_qualification:
            uncertain_reasons.append(
                f"Could not automatically parse qualification requirement: "
                f"'{notification.educational_qualification[:100]}'. Please verify manually."
            )
            checks.append({
                "check": "qualification", "result": "uncertain",
                "detail": "Qualification text present but could not be parsed automatically."
            })
        else:
            info_missing.append("Educational qualification not specified in the advertisement.")
            checks.append({
                "check": "qualification", "result": "not_specified",
                "detail": "No educational qualification found in notification."
            })

    # --- Experience Check ---
    if notification.experience_years and notification.experience_years > 0:
        uncertain_reasons.append(
            f"This position requires {notification.experience_years} year(s) of experience. "
            f"Please verify you meet this requirement."
        )
        checks.append({
            "check": "experience", "result": "uncertain",
            "detail": f"Requires {notification.experience_years} year(s) experience."
        })

    # --- Domicile Check ---
    if notification.state and profile.domicile_state:
        if notification.state.lower().strip() == profile.domicile_state.lower().strip():
            msg = f"Your domicile state ({profile.domicile_state}) matches."
            pass_reasons.append(msg)
            checks.append({"check": "domicile", "result": "pass", "detail": msg})
        else:
            # Some notifications are open to all states
            uncertain_reasons.append(
                f"Notification mentions '{notification.state}' but your domicile "
                f"is '{profile.domicile_state}'. Verify if the position is "
                f"restricted by domicile."
            )
            checks.append({
                "check": "domicile", "result": "uncertain",
                "detail": f"State mismatch: notification says '{notification.state}', "
                          f"profile says '{profile.domicile_state}'."
            })

    # --- Determine Overall Result ---
    if fail_reasons:
        explanation_parts = ["Not Eligible."]
        explanation_parts.extend(fail_reasons)
        if pass_reasons:
            explanation_parts.append("However, some criteria are met:")
            explanation_parts.extend(pass_reasons)
        explanation_parts.append(
            "\nThis is an automated preliminary assessment. "
            "The official recruitment advertisement takes precedence."
        )
        return MatchResult(
            match=EligibilityMatch.NOT_ELIGIBLE,
            explanation=" ".join(explanation_parts),
            checks=checks,
        )

    # Missing mandatory user fields when notification specifies requirements
    missing_user_fields = []
    if notification.max_age and not profile.date_of_birth:
        missing_user_fields.append("Date of birth not provided; age eligibility could not be verified.")
    if required_level and not user_highest:
        missing_user_fields.append("Educational qualifications not provided in profile; qualification requirement could not be verified.")

    if missing_user_fields:
        explanation_parts = ["Insufficient Information."]
        explanation_parts.extend(missing_user_fields)
        if pass_reasons:
            explanation_parts.append("Matched criteria:")
            explanation_parts.extend(pass_reasons)
        explanation_parts.append(
            "\nPlease complete your profile to enable full eligibility assessment. "
            "This is an automated preliminary assessment. "
            "The official recruitment advertisement takes precedence."
        )
        return MatchResult(
            match=EligibilityMatch.INSUFFICIENT_INFO,
            explanation=" ".join(explanation_parts),
            checks=checks,
        )

    if not pass_reasons and not uncertain_reasons:
        # No checks could be performed
        return MatchResult(
            match=EligibilityMatch.INSUFFICIENT_INFO,
            explanation=(
                "Insufficient information to assess eligibility. "
                + " ".join(info_missing)
                + " Please review the official advertisement for detailed requirements. "
                "This is an automated preliminary assessment."
            ),
            checks=checks,
        )

    if uncertain_reasons:
        explanation_parts = ["Possibly Eligible."]
        if pass_reasons:
            explanation_parts.extend(pass_reasons)
        explanation_parts.append("Some conditions need manual verification:")
        explanation_parts.extend(uncertain_reasons)
        explanation_parts.append(
            "\nThis is an automated preliminary assessment. "
            "The official recruitment advertisement takes precedence."
        )
        return MatchResult(
            match=EligibilityMatch.POSSIBLY_ELIGIBLE,
            explanation=" ".join(explanation_parts),
            checks=checks,
        )

    # All checks passed
    explanation_parts = ["Likely Eligible."]
    explanation_parts.extend(pass_reasons)
    if info_missing:
        explanation_parts.append("Note: " + " ".join(info_missing))
    explanation_parts.append(
        "Confirm the official category and domicile conditions before applying. "
        "This is an automated preliminary assessment. "
        "The official recruitment advertisement takes precedence."
    )
    return MatchResult(
        match=EligibilityMatch.LIKELY_ELIGIBLE,
        explanation=" ".join(explanation_parts),
        checks=checks,
    )
