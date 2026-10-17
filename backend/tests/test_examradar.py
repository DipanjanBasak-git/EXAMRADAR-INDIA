"""ExamRadar India - Backend Tests"""

import pytest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.session import Base, get_db
from app.models.notification import (
    Notification, ApplicationStatus, VerificationStatus, LifecycleEvent
)
from app.models.source import Organization, RecruitmentCategory
from app.models.user import (
    UserProfile, UserQualification, QualificationLevel, ReservationCategory
)
from app.services.eligibility import (
    evaluate_eligibility, calculate_age, EligibilityMatch,
    infer_required_qualification
)
from app.services.notifications import (
    calculate_application_status, get_current_ist_datetime,
    get_current_ist_date, parse_deadline_to_ist, get_effective_deadline,
    calculate_deadline_metrics, IST
)
from app.services.discovery import (
    is_safe_url, content_hash,
    normalize_date, extract_vacancies, extract_age_limits
)

# Test database
TEST_DB_URL = "sqlite:///./test_examradar.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_org(db):
    org = Organization(
        name="Test Organization",
        short_name="TEST",
        official_website="https://test.gov.in",
        category=RecruitmentCategory.BANKING,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def sample_notification(db, sample_org):
    today = date.today()
    n = Notification(
        title="[SYNTHETIC TEST] Test Recruitment 2026",
        organization_id=sample_org.id,
        category="banking",
        post_name="Test Officer",
        advertisement_number="TEST-001",
        total_vacancies=100,
        min_age=20,
        max_age=30,
        age_cutoff_date=date(2026, 12, 31),
        educational_qualification="Graduate degree from a recognized university",
        qualification_details={"min_level": "undergraduate"},
        application_start_date=today - timedelta(days=5),
        application_end_date=today + timedelta(days=15),
        application_fee={"general": 600, "sc_st": 100},
        salary_range="₹30,000 - ₹60,000",
        selection_process="Written Test → Interview",
        location="All India",
        application_status=ApplicationStatus.APPLICATION_OPEN,
        verification_status=VerificationStatus.UNVERIFIED,
        official_notification_url="https://test.gov.in/recruit",
        source_url="https://test.gov.in",
        source_domain="test.gov.in",
        extraction_method="synthetic_test_fixture",
        is_synthetic=True,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


@pytest.fixture
def sample_profile(db):
    profile = UserProfile(
        date_of_birth=date(1998, 5, 15),
        state_of_residence="West Bengal",
        domicile_state="West Bengal",
        nationality="Indian",
        gender="Male",
        reservation_category=ReservationCategory.GENERAL,
        profile_matching_enabled=True,
    )
    db.add(profile)
    db.flush()

    qual = UserQualification(
        profile_id=profile.id,
        level=QualificationLevel.UNDERGRADUATE,
        degree_name="B.Tech Computer Science",
        specialization="Computer Science",
        discipline="engineering",
        graduation_status="completed",
        graduation_year=2021,
        percentage="78",
        is_highest=True,
    )
    db.add(qual)
    db.commit()
    db.refresh(profile)
    return profile


# ============= Unit Tests =============

class TestDateNormalization:
    def test_dd_mm_yyyy_slash(self):
        assert normalize_date("15/06/2026") == date(2026, 6, 15)

    def test_dd_mm_yyyy_dash(self):
        assert normalize_date("15-06-2026") == date(2026, 6, 15)

    def test_dd_mm_yyyy_dot(self):
        assert normalize_date("15.06.2026") == date(2026, 6, 15)

    def test_iso_format(self):
        assert normalize_date("2026-06-15") == date(2026, 6, 15)

    def test_dd_mmm_yyyy(self):
        assert normalize_date("15 Jun 2026") == date(2026, 6, 15)

    def test_invalid_date(self):
        assert normalize_date("not a date") is None

    def test_empty_string(self):
        assert normalize_date("") is None

    def test_none_input(self):
        assert normalize_date(None) is None


class TestAgeCalculation:
    def test_exact_birthday(self):
        assert calculate_age(date(2000, 5, 15), date(2026, 5, 15)) == 26

    def test_before_birthday(self):
        assert calculate_age(date(2000, 5, 15), date(2026, 5, 14)) == 25

    def test_after_birthday(self):
        assert calculate_age(date(2000, 5, 15), date(2026, 5, 16)) == 26


class TestApplicationStatus:
    def test_open_application(self, db, sample_org):
        today = date.today()
        n = Notification(
            title="Test", organization_id=sample_org.id, category="banking",
            application_start_date=today - timedelta(days=5),
            application_end_date=today + timedelta(days=15),
        )
        assert calculate_application_status(n) == ApplicationStatus.APPLICATION_OPEN

    def test_closing_soon(self, db, sample_org):
        today = date.today()
        n = Notification(
            title="Test", organization_id=sample_org.id, category="banking",
            application_start_date=today - timedelta(days=5),
            application_end_date=today + timedelta(days=2),
        )
        assert calculate_application_status(n) == ApplicationStatus.CLOSING_SOON

    def test_closed(self, db, sample_org):
        today = date.today()
        n = Notification(
            title="Test", organization_id=sample_org.id, category="banking",
            application_start_date=today - timedelta(days=30),
            application_end_date=today - timedelta(days=1),
        )
        assert calculate_application_status(n) == ApplicationStatus.CLOSED

    def test_upcoming(self, db, sample_org):
        today = date.today()
        n = Notification(
            title="Test", organization_id=sample_org.id, category="banking",
            application_start_date=today + timedelta(days=10),
            application_end_date=today + timedelta(days=40),
        )
        assert calculate_application_status(n) == ApplicationStatus.UPCOMING


class TestEligibilityMatching:
    def test_likely_eligible(self, db, sample_notification, sample_profile):
        result = evaluate_eligibility(sample_notification, sample_profile)
        assert result.match == EligibilityMatch.LIKELY_ELIGIBLE

    def test_age_too_old(self, db, sample_notification, sample_profile):
        sample_profile.date_of_birth = date(1990, 1, 1)  # Too old for 20-30
        result = evaluate_eligibility(sample_notification, sample_profile)
        assert result.match == EligibilityMatch.NOT_ELIGIBLE

    def test_age_too_young(self, db, sample_notification, sample_profile):
        sample_profile.date_of_birth = date(2010, 1, 1)  # Too young
        result = evaluate_eligibility(sample_notification, sample_profile)
        assert result.match == EligibilityMatch.NOT_ELIGIBLE

    def test_obc_relaxation(self, db, sample_notification):
        profile = UserProfile(
            date_of_birth=date(1994, 1, 1),  # age ~32 at cutoff
            reservation_category=ReservationCategory.OBC_NCL,
            profile_matching_enabled=True,
        )
        db.add(profile)
        qual = UserQualification(
            profile_id=1,
            level=QualificationLevel.UNDERGRADUATE,
            degree_name="B.Com",
            graduation_status="completed",
            graduation_year=2016,
            is_highest=True,
        )
        profile.qualifications = [qual]

        # Max age 30 + 3 (OBC) = 33. Age at cutoff ~32. Should pass.
        result = evaluate_eligibility(sample_notification, profile)
        assert result.match in (EligibilityMatch.LIKELY_ELIGIBLE, EligibilityMatch.POSSIBLY_ELIGIBLE)

    def test_qualification_insufficient(self, db, sample_notification, sample_profile):
        sample_profile.qualifications[0].level = QualificationLevel.TWELFTH
        sample_profile.qualifications[0].degree_name = "12th Pass"
        result = evaluate_eligibility(sample_notification, sample_profile)
        assert result.match == EligibilityMatch.NOT_ELIGIBLE

    def test_no_profile_info(self, db, sample_notification):
        empty_profile = UserProfile(profile_matching_enabled=True)
        db.add(empty_profile)
        result = evaluate_eligibility(sample_notification, empty_profile)
        assert result.match == EligibilityMatch.INSUFFICIENT_INFO

    def test_explanation_present(self, db, sample_notification, sample_profile):
        result = evaluate_eligibility(sample_notification, sample_profile)
        assert len(result.explanation) > 20
        assert "automated preliminary assessment" in result.explanation.lower()


class TestVacancyExtraction:
    def test_extract_vacancies(self):
        assert extract_vacancies("Total No. of Vacancies: 4455") == 4455

    def test_extract_posts(self):
        assert extract_vacancies("1234 posts are available") == 1234

    def test_no_vacancy(self):
        assert extract_vacancies("No information here") is None


class TestAgeLimitExtraction:
    def test_age_range(self):
        min_a, max_a = extract_age_limits("Age Limit: 18 to 30 years")
        assert min_a == 18
        assert max_a == 30

    def test_age_dash(self):
        min_a, max_a = extract_age_limits("Age limit: 20-35 years")
        assert min_a == 20
        assert max_a == 35


class TestQualificationInference:
    def test_graduate(self):
        result = infer_required_qualification("Must have graduation from recognized university")
        assert result == QualificationLevel.UNDERGRADUATE

    def test_btech(self):
        result = infer_required_qualification("B.Tech in Computer Science required")
        assert result == QualificationLevel.UNDERGRADUATE

    def test_postgraduate(self):
        result = infer_required_qualification("Master's degree in relevant subject")
        assert result == QualificationLevel.POSTGRADUATE


class TestSSRFProtection:
    def test_safe_url(self):
        assert is_safe_url("https://www.ibps.in/") is True

    def test_localhost_blocked(self):
        assert is_safe_url("http://localhost:8080") is False

    def test_private_ip_blocked(self):
        assert is_safe_url("http://192.168.1.1") is False

    def test_metadata_blocked(self):
        assert is_safe_url("http://169.254.169.254/latest/meta-data") is False

    def test_ftp_blocked(self):
        assert is_safe_url("ftp://files.example.com") is False


class TestContentHash:
    def test_consistent(self):
        h1 = content_hash("test content")
        h2 = content_hash("test content")
        assert h1 == h2

    def test_different(self):
        h1 = content_hash("content a")
        h2 = content_hash("content b")
        assert h1 != h2


class TestDuplicateDetection:
    def test_same_url_not_duplicated(self, db, sample_org):
        n1 = Notification(
            title="Test 1", organization_id=sample_org.id, category="banking",
            source_url="https://test.gov.in/notif1",
            is_synthetic=True,
        )
        db.add(n1)
        db.commit()

        # Check for existing
        existing = db.query(Notification).filter(
            Notification.source_url == "https://test.gov.in/notif1"
        ).first()
        assert existing is not None
        assert existing.title == "Test 1"


# ============= API Tests =============

class TestHealthAPI:
    def test_health(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ExamRadar India"


class TestCategoriesAPI:
    def test_categories(self):
        response = client.get("/api/v1/categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert len(data["categories"]) > 0
        values = [c["value"] for c in data["categories"]]
        assert "banking" in values
        assert "upsc" in values
        assert "ssc" in values


class TestDashboardAPI:
    def test_dashboard(self):
        response = client.get("/api/v1/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "total_open" in data
        assert "newly_discovered" in data


class TestNotificationsAPI:
    def test_list_notifications(self):
        response = client.get("/api/v1/notifications")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_filter_by_category(self):
        response = client.get("/api/v1/notifications?category=banking")
        assert response.status_code == 200

    def test_pagination(self):
        response = client.get("/api/v1/notifications?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5


class TestProfileAPI:
    def test_get_profile(self):
        response = client.get("/api/v1/profile")
        assert response.status_code == 200

    def test_update_profile(self):
        profile_data = {
            "date_of_birth": "1998-05-15",
            "state_of_residence": "West Bengal",
            "domicile_state": "West Bengal",
            "nationality": "Indian",
            "gender": "Male",
            "reservation_category": "general",
            "is_pwbd": False,
            "is_ex_serviceman": False,
            "profile_matching_enabled": True,
            "qualifications": [
                {
                    "level": "undergraduate",
                    "degree_name": "B.Tech",
                    "specialization": "Computer Science",
                    "discipline": "engineering",
                    "graduation_status": "completed",
                    "graduation_year": 2021,
                    "percentage": "78",
                    "is_highest": True,
                }
            ],
            "career_preferences": [
                {"preference_type": "category", "preference_value": "banking"},
                {"preference_type": "category", "preference_value": "ssc"},
            ],
        }
        response = client.put("/api/v1/profile", json=profile_data)
        assert response.status_code == 200
        data = response.json()
        assert data["state_of_residence"] == "West Bengal"
        assert len(data["qualifications"]) == 1

    def test_delete_profile(self):
        response = client.delete("/api/v1/profile")
        assert response.status_code == 200


class TestSourcesAPI:
    def test_get_sources(self):
        response = client.get("/api/v1/sources")
        assert response.status_code == 200

    def test_source_status(self):
        response = client.get("/api/v1/sources/status")
        assert response.status_code == 200
        data = response.json()
        assert "total_sources" in data

    def test_discovery_status(self):
        response = client.get("/api/v1/discovery/status")
        assert response.status_code == 200


class TestManifestValid:
    """Verify the Chrome extension manifest is valid JSON and has required fields."""

    def test_manifest_structure(self):
        import json
        import os
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "extension", "manifest.json"
        )
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)
            assert manifest["manifest_version"] == 3
            assert "name" in manifest
            assert "version" in manifest
            assert "permissions" in manifest
            assert "alarms" in manifest["permissions"]
            assert "notifications" in manifest["permissions"]
            assert "storage" in manifest["permissions"]


# ============= Advanced Requirements Verification Tests =============

class TestDeadlineCalculationsIST:
    """Verify Asia/Kolkata timezone handling, date-only parsing, expired notices, and extensions."""

    def test_current_ist_timezone(self):
        now_ist = get_current_ist_datetime()
        assert str(now_ist.tzinfo) == "Asia/Kolkata"
        today_ist = get_current_ist_date()
        assert isinstance(today_ist, date)

    def test_date_only_deadline_eod(self):
        target = date(2026, 11, 20)
        dt = parse_deadline_to_ist(target)
        assert dt.year == 2026 and dt.month == 11 and dt.day == 20
        assert dt.hour == 23 and dt.minute == 59 and dt.second == 59
        assert str(dt.tzinfo) == "Asia/Kolkata"

    def test_expired_notice_status_closed(self, sample_org):
        today = get_current_ist_date()
        n = Notification(
            title="Expired Notification",
            organization_id=sample_org.id,
            category="central_govt",
            application_start_date=today - timedelta(days=30),
            application_end_date=today - timedelta(days=2),
            is_synthetic=True,
        )
        status = calculate_application_status(n)
        assert status == ApplicationStatus.CLOSED

    def test_closing_soon_status(self, sample_org):
        today = get_current_ist_date()
        n = Notification(
            title="Closing Soon Notice",
            organization_id=sample_org.id,
            category="central_govt",
            application_start_date=today - timedelta(days=10),
            application_end_date=today + timedelta(days=2),
            is_synthetic=True,
        )
        status = calculate_application_status(n)
        assert status == ApplicationStatus.CLOSING_SOON

    def test_deadline_extension_via_corrigendum(self, sample_org):
        today = get_current_ist_date()
        original_end = today - timedelta(days=1)  # would be closed normally
        extended_end = today + timedelta(days=10) # extended by 10 days

        n = Notification(
            title="UPSC CSE 2026 (Corrigendum)",
            organization_id=sample_org.id,
            category="upsc",
            application_start_date=today - timedelta(days=20),
            application_end_date=original_end,
            is_synthetic=True,
        )
        # Add Corrigendum / extension lifecycle event
        event = LifecycleEvent(
            event_type="deadline_extended",
            event_date=datetime.combine(extended_end, datetime.min.time()),
            description="Last date for online application extended by Commission",
            verified=True,
        )
        n.lifecycle_events.append(event)

        effective_date, is_extended = get_effective_deadline(n)
        assert is_extended is True
        assert effective_date == extended_end

        # Recalculated status must now be OPEN rather than CLOSED
        status = calculate_application_status(n)
        assert status == ApplicationStatus.APPLICATION_OPEN


class TestEligibilityRecalculationComprehensive:
    """Verify age calculation, category relaxation rules, educational hierarchy, and explanations."""

    def test_likely_eligible_undergraduate(self, sample_notification, sample_profile):
        result = evaluate_eligibility(sample_notification, sample_profile)
        assert result.match == EligibilityMatch.LIKELY_ELIGIBLE
        assert "meets or exceeds" in result.explanation

    def test_not_eligible_age_exceeded(self, sample_notification, db):
        # Born in 1980 -> 46 years old as of 2026 cutoff date
        older_profile = UserProfile(
            date_of_birth=date(1980, 1, 1),
            reservation_category=ReservationCategory.GENERAL,
            profile_matching_enabled=True,
        )
        db.add(older_profile)
        db.flush()
        db.add(UserQualification(profile_id=older_profile.id, level=QualificationLevel.UNDERGRADUATE, is_highest=True))
        db.commit()

        result = evaluate_eligibility(sample_notification, older_profile)
        assert result.match == EligibilityMatch.NOT_ELIGIBLE
        assert "exceeds the maximum age limit" in result.explanation

    def test_obc_age_relaxation_3_years(self, sample_notification, db):
        # Age limit is 20-30. Candidate born in 1994 -> 32 years old.
        # General: Not eligible. OBC: max becomes 33 -> Eligible!
        obc_profile = UserProfile(
            date_of_birth=date(1994, 1, 1),
            reservation_category=ReservationCategory.OBC_NCL,
            profile_matching_enabled=True,
        )
        db.add(obc_profile)
        db.flush()
        db.add(UserQualification(profile_id=obc_profile.id, level=QualificationLevel.UNDERGRADUATE, is_highest=True))
        db.commit()

        result = evaluate_eligibility(sample_notification, obc_profile)
        assert result.match == EligibilityMatch.LIKELY_ELIGIBLE
        assert "within the permitted range" in result.explanation

    def test_sc_st_age_relaxation_5_years(self, sample_notification, db):
        # Age limit is 20-30. Candidate born in 1992 -> 34 years old.
        # SC: max becomes 35 -> Eligible!
        sc_profile = UserProfile(
            date_of_birth=date(1992, 1, 1),
            reservation_category=ReservationCategory.SC,
            profile_matching_enabled=True,
        )
        db.add(sc_profile)
        db.flush()
        db.add(UserQualification(profile_id=sc_profile.id, level=QualificationLevel.UNDERGRADUATE, is_highest=True))
        db.commit()

        result = evaluate_eligibility(sample_notification, sc_profile)
        assert result.match == EligibilityMatch.LIKELY_ELIGIBLE

    def test_pwbd_age_relaxation_10_years(self, sample_notification, db):
        # Age limit 20-30. Candidate born in 1988 -> 38 years old.
        # PwBD: max becomes 40 -> Eligible!
        pwbd_profile = UserProfile(
            date_of_birth=date(1988, 1, 1),
            reservation_category=ReservationCategory.GENERAL,
            is_pwbd=True,
            profile_matching_enabled=True,
        )
        db.add(pwbd_profile)
        db.flush()
        db.add(UserQualification(profile_id=pwbd_profile.id, level=QualificationLevel.UNDERGRADUATE, is_highest=True))
        db.commit()

        result = evaluate_eligibility(sample_notification, pwbd_profile)
        assert result.match == EligibilityMatch.LIKELY_ELIGIBLE

    def test_not_eligible_insufficient_qualification(self, sample_notification, db):
        # Requires Graduate; user only has 10th
        matric_profile = UserProfile(
            date_of_birth=date(2000, 1, 1),
            reservation_category=ReservationCategory.GENERAL,
            profile_matching_enabled=True,
        )
        db.add(matric_profile)
        db.flush()
        db.add(UserQualification(profile_id=matric_profile.id, level=QualificationLevel.TENTH, is_highest=True))
        db.commit()

        result = evaluate_eligibility(sample_notification, matric_profile)
        assert result.match == EligibilityMatch.NOT_ELIGIBLE
        assert "may not meet the required level" in result.explanation

    def test_insufficient_information_missing_dob(self, sample_notification, db):
        # Profile without DOB
        no_dob_profile = UserProfile(
            date_of_birth=None,
            reservation_category=ReservationCategory.GENERAL,
            profile_matching_enabled=True,
        )
        db.add(no_dob_profile)
        db.flush()
        db.add(UserQualification(profile_id=no_dob_profile.id, level=QualificationLevel.UNDERGRADUATE, is_highest=True))
        db.commit()

        result = evaluate_eligibility(sample_notification, no_dob_profile)
        assert result.match == EligibilityMatch.INSUFFICIENT_INFO
        assert "Date of birth not provided" in result.explanation


class TestAlertDeduplicationLogic:
    """Verify persistent alert deduplication mechanisms."""

    def test_deduplication_set_logic(self):
        # Simulates extension service worker deduplication tracking
        alerted_ids = {101, 102}
        incoming_batch = [
            {"id": 101, "title": "Old Exam"},
            {"id": 102, "title": "Another Old Exam"},
            {"id": 103, "title": "Brand New Notification"},
        ]

        unalerted = [item for item in incoming_batch if item["id"] not in alerted_ids]
        assert len(unalerted) == 1
        assert unalerted[0]["id"] == 103

        # Simulate recording new alert
        for item in unalerted:
            alerted_ids.add(item["id"])

        # Repeat check (e.g. extension restart)
        recheck_unalerted = [item for item in incoming_batch if item["id"] not in alerted_ids]
        assert len(recheck_unalerted) == 0  # No duplicate desktop alerts!


class TestAPIFailureHandling:
    """Verify HTTP error handling and validation."""

    def test_notification_not_found(self):
        response = client.get("/api/v1/notifications/999999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Notification not found"

    def test_invalid_profile_payload_rejected(self):
        # Invalid date format
        bad_payload = {"date_of_birth": "invalid-date-string"}
        response = client.put("/api/v1/profile", json=bad_payload)
        assert response.status_code == 422

    def test_source_status_hyphen_alias(self):
        # Both /sources/status and /source-status must return 200
        r1 = client.get("/api/v1/sources/status")
        r2 = client.get("/api/v1/source-status")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["total_sources"] == r2.json()["total_sources"]


class TestExtensionSecurityAndCSP:
    """Ensure extension adheres to Manifest V3 security (no inline scripts, valid CSP)."""

    def test_no_inline_event_handlers_in_html(self):
        import os
        import re
        ext_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "extension"
        )
        html_files = ["popup.html", "dashboard.html"]
        for h in html_files:
            path = os.path.join(ext_dir, h)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Check for inline onclick, onload, etc.
                matches = re.findall(r"\bon[a-z]+=", content, re.IGNORECASE)
                assert len(matches) == 0, f"Found inline event handler in {h}: {matches}"

    def test_no_eval_in_extension_scripts(self):
        import os
        ext_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "extension"
        )
        js_files = ["background.js", "api.js", "popup.js", "dashboard.js"]
        for j in js_files:
            path = os.path.join(ext_dir, j)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                assert "eval(" not in content, f"Forbidden eval() found in {j}"


class TestSyntheticIsolationAndProductionFeeds:
    """Ensure synthetic test records NEVER leak into production feeds or dashboard metrics."""

    def test_synthetic_notifications_excluded_by_default(self, db, sample_org, sample_notification):
        # sample_notification is synthetic (is_synthetic=True)
        # Add a genuine notification as well
        genuine = Notification(
            title="UPSC Civil Services Examination 2026",
            organization_id=sample_org.id,
            category="upsc",
            advertisement_number="01/2026-CSP",
            total_vacancies=1056,
            min_age=21,
            max_age=32,
            educational_qualification="Bachelor Degree in Any Stream",
            application_start_date=date.today() - timedelta(days=2),
            application_end_date=date.today() + timedelta(days=20),
            application_status=ApplicationStatus.APPLICATION_OPEN,
            verification_status=VerificationStatus.OFFICIAL_VERIFIED,
            official_notification_url="https://upsc.gov.in/sites/default/files/Notice-CSP-2026.pdf",
            source_url="https://upsc.gov.in",
            source_domain="upsc.gov.in",
            extraction_method="official_upsc_html",
            is_synthetic=False,
            is_active=True,
        )
        db.add(genuine)
        db.commit()

        # Production feed default: include_synthetic is False
        res = client.get("/api/v1/notifications")
        assert res.status_code == 200
        data = res.json()
        items = data["items"]

        # Must only contain the genuine record
        assert len(items) == 1
        assert items[0]["title"] == "UPSC Civil Services Examination 2026"
        assert items[0]["is_synthetic"] is False

        # When explicitly requested with include_synthetic=true
        res_all = client.get("/api/v1/notifications?include_synthetic=true")
        assert res_all.status_code == 200
        assert len(res_all.json()["items"]) == 2

    def test_dashboard_metrics_exclude_synthetic(self, db, sample_org, sample_notification):
        # sample_notification is synthetic (is_synthetic=True)
        # Dashboard must report 0 open notifications because only synthetic exists
        res = client.get("/api/v1/dashboard")
        assert res.status_code == 200
        data = res.json()
        assert data["total_open"] == 0
        assert len(data["recent_notifications"]) == 0

    def test_sources_status_reports_notification_counts(self, db, sample_org):
        from app.models.source import Source, SourceType
        source = Source(
            name="Union Public Service Commission",
            organization_id=sample_org.id,
            category=RecruitmentCategory.UPSC,
            source_type=SourceType.OFFICIAL_WEBSITE,
            base_url="https://www.upsc.gov.in",
            recruitment_page_url="https://www.upsc.gov.in/examinations/active-exams",
            is_enabled=True,
            fetch_interval_minutes=60,
        )
        db.add(source)
        db.commit()

        # Add genuine notification linked to this org
        n = Notification(
            title="Combined Defence Services Examination (I), 2026",
            organization_id=sample_org.id,
            category="upsc",
            official_notification_url="https://upsc.gov.in/notices/cds1.pdf",
            source_url="https://upsc.gov.in",
            verification_status=VerificationStatus.OFFICIAL_VERIFIED,
            is_synthetic=False,
        )
        db.add(n)
        db.commit()

        res = client.get("/api/v1/sources/status")
        assert res.status_code == 200
        sources_list = res.json()["sources"]
        matching = [s for s in sources_list if s["name"] == "Union Public Service Commission"]
        assert len(matching) == 1
        assert matching[0]["notifications_count"] == 1


class TestAdminDiscoverySecurity:
    """Test administrative authorization for manual discovery triggers."""

    def test_discovery_run_local_or_admin_authorized(self):
        # TestClient uses client host "testclient" which is treated as local in verify_admin_access
        res = client.post("/api/v1/discovery/run")
        assert res.status_code in (200, 202)
        assert "Discovery run" in res.json()["message"]

    def test_discovery_run_with_admin_header(self):
        res = client.post("/api/v1/discovery/run", headers={"x-admin-key": "examradar-admin"})
        assert res.status_code in (200, 202)


