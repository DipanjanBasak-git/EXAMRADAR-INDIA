"""ExamRadar India - Seed Data

Seeds the initial source registry and synthetic test fixtures.
All synthetic notifications are clearly marked with is_synthetic=True.
"""

import logging
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from app.models.source import Organization, Source, RecruitmentCategory, SourceType
from app.models.notification import (
    Notification, ApplicationStatus, VerificationStatus
)

logger = logging.getLogger("examradar.seed")


ORGANIZATIONS = [
    # Banking
    {
        "name": "Institute of Banking Personnel Selection",
        "short_name": "IBPS",
        "official_website": "https://www.ibps.in",
        "category": RecruitmentCategory.BANKING,
        "description": "Conducts recruitment exams for public sector banks.",
    },
    {
        "name": "State Bank of India",
        "short_name": "SBI",
        "official_website": "https://sbi.co.in/web/careers",
        "category": RecruitmentCategory.BANKING,
        "description": "India's largest public sector bank.",
    },
    {
        "name": "Reserve Bank of India",
        "short_name": "RBI",
        "official_website": "https://www.rbi.org.in",
        "category": RecruitmentCategory.BANKING,
        "description": "India's central banking institution.",
    },
    {
        "name": "National Bank for Agriculture and Rural Development",
        "short_name": "NABARD",
        "official_website": "https://www.nabard.org",
        "category": RecruitmentCategory.BANKING,
        "description": "Development financial institution for agriculture and rural development.",
    },
    # UPSC
    {
        "name": "Union Public Service Commission",
        "short_name": "UPSC",
        "official_website": "https://www.upsc.gov.in",
        "category": RecruitmentCategory.UPSC,
        "description": "Central recruiting agency for Group A and Group B gazetted posts.",
    },
    # SSC
    {
        "name": "Staff Selection Commission",
        "short_name": "SSC",
        "official_website": "https://ssc.gov.in",
        "category": RecruitmentCategory.SSC,
        "description": "Recruits staff for Group C and Group D posts.",
    },
    # Railways
    {
        "name": "Railway Recruitment Board",
        "short_name": "RRB",
        "official_website": "https://www.rrbcdg.gov.in",
        "category": RecruitmentCategory.RAILWAYS,
        "description": "Conducts railway recruitment examinations.",
    },
    # Defence
    {
        "name": "Indian Army",
        "short_name": "Indian Army",
        "official_website": "https://www.joinindianarmy.nic.in",
        "category": RecruitmentCategory.DEFENCE,
        "description": "Indian Army recruitment portal.",
    },
    {
        "name": "Indian Navy",
        "short_name": "Indian Navy",
        "official_website": "https://www.joinindiannavy.gov.in",
        "category": RecruitmentCategory.DEFENCE,
        "description": "Indian Navy recruitment portal.",
    },
    {
        "name": "Indian Air Force",
        "short_name": "IAF",
        "official_website": "https://afcat.cdac.in",
        "category": RecruitmentCategory.DEFENCE,
        "description": "Indian Air Force recruitment via AFCAT.",
    },
    # Central Govt
    {
        "name": "Employment News",
        "short_name": "Employment News",
        "official_website": "https://www.employmentnews.gov.in",
        "category": RecruitmentCategory.CENTRAL_GOVT,
        "description": "Official gazette for government vacancies.",
    },
    {
        "name": "National Career Service",
        "short_name": "NCS",
        "official_website": "https://www.ncs.gov.in",
        "category": RecruitmentCategory.CENTRAL_GOVT,
        "description": "National portal for job seekers and employers.",
    },
    # State Govt
    {
        "name": "West Bengal Public Service Commission",
        "short_name": "WBPSC",
        "official_website": "https://www.pscwbonline.gov.in",
        "category": RecruitmentCategory.STATE_GOVT,
        "description": "State PSC for West Bengal government recruitment.",
    },
    # PSU / Research
    {
        "name": "Defence Research and Development Organisation",
        "short_name": "DRDO",
        "official_website": "https://www.drdo.gov.in",
        "category": RecruitmentCategory.RESEARCH,
        "description": "India's premier defence R&D organization.",
    },
    {
        "name": "Indian Space Research Organisation",
        "short_name": "ISRO",
        "official_website": "https://www.isro.gov.in",
        "category": RecruitmentCategory.RESEARCH,
        "description": "India's national space agency.",
    },
    {
        "name": "Oil and Natural Gas Corporation",
        "short_name": "ONGC",
        "official_website": "https://www.ongcindia.com",
        "category": RecruitmentCategory.PSU,
        "description": "India's largest oil and gas exploration PSU.",
    },
]


SOURCES = [
    {
        "org_short": "UPSC",
        "name": "UPSC Examinations & Recruitment",
        "base_url": "https://www.upsc.gov.in",
        "recruitment_page_url": "https://www.upsc.gov.in/",
        "fetch_interval_minutes": 180,
        "parsing_strategy": "upsc_html",
    },
    {
        "org_short": "IBPS",
        "name": "IBPS Official Notifications",
        "base_url": "https://www.ibps.in",
        "recruitment_page_url": "https://www.ibps.in/",
        "fetch_interval_minutes": 180,
        "parsing_strategy": "ibps_html",
    },
    {
        "org_short": "RRB",
        "name": "Railway Recruitment Board (Chandigarh)",
        "base_url": "https://rrbcdg.gov.in",
        "recruitment_page_url": "https://rrb.indianrailways.gov.in/chandigarh",
        "fetch_interval_minutes": 180,
        "parsing_strategy": "rrb_html",
    },
    {
        "org_short": "SBI",
        "name": "SBI Careers - Current Openings",
        "base_url": "https://sbi.bank.in/web/careers",
        "recruitment_page_url": "https://sbi.bank.in/web/careers/current-openings",
        "fetch_interval_minutes": 180,
        "parsing_strategy": "sbi_html",
    },
    {
        "org_short": "WBPSC",
        "name": "WBPSC Official Advertisements",
        "base_url": "https://psc.wb.gov.in",
        "recruitment_page_url": "https://psc.wb.gov.in/",
        "fetch_interval_minutes": 180,
        "parsing_strategy": "wbpsc_html",
    },
    {
        "org_short": "ISRO",
        "name": "ISRO Recruitment Portal",
        "base_url": "https://www.isro.gov.in",
        "recruitment_page_url": "https://www.isro.gov.in/Careers.html",
        "fetch_interval_minutes": 360,
        "parsing_strategy": "isro_html",
    },
    {
        "org_short": "DRDO",
        "name": "DRDO Recruitment & Assessment Centre (RAC)",
        "base_url": "https://rac.gov.in",
        "recruitment_page_url": "https://rac.gov.in/index.php?lang=en&id=0",
        "fetch_interval_minutes": 360,
        "parsing_strategy": "drdo_html",
    },
    {
        "org_short": "SSC",
        "name": "Staff Selection Commission (Official)",
        "base_url": "https://ssc.gov.in",
        "recruitment_page_url": "https://ssc.gov.in/",
        "fetch_interval_minutes": 360,
        "parsing_strategy": "generic_html",
    },
    {
        "org_short": "RBI",
        "name": "RBI Official Opportunities & Vacancies",
        "base_url": "https://opportunities.rbi.org.in",
        "recruitment_page_url": "https://opportunities.rbi.org.in/scripts/vacancies.aspx",
        "fetch_interval_minutes": 180,
        "parsing_strategy": "rbi_html",
    },
    {
        "org_short": "Indian Army",
        "name": "Join Indian Army Portal",
        "base_url": "https://www.joinindianarmy.nic.in",
        "recruitment_page_url": "https://www.joinindianarmy.nic.in/",
        "fetch_interval_minutes": 720,
        "parsing_strategy": "generic_html",
    },
]


def purge_synthetic_notifications(db: Session) -> int:
    """
    Remove all synthetic test records from the production database.
    Preserves genuine recruitment records, organizations, sources, and user preferences.
    """
    from app.models.user import SavedNotification
    from app.models.notification import LifecycleEvent

    synthetic_notifs = db.query(Notification).filter(
        (Notification.is_synthetic == True) |
        (Notification.title.like("%[SYNTHETIC TEST]%"))
    ).all()

    if not synthetic_notifs:
        return 0

    synthetic_ids = [n.id for n in synthetic_notifs]

    # Clean up associated child records
    db.query(SavedNotification).filter(SavedNotification.notification_id.in_(synthetic_ids)).delete(synchronize_session=False)
    db.query(LifecycleEvent).filter(LifecycleEvent.notification_id.in_(synthetic_ids)).delete(synchronize_session=False)

    # Delete the synthetic notifications
    count = db.query(Notification).filter(Notification.id.in_(synthetic_ids)).delete(synchronize_session=False)
    db.commit()
    logger.info(f"Purged {count} synthetic test notifications from the production database.")
    return count


def purge_non_job_notifications(db: Session) -> int:
    """Purge junk non-recruitment records (media interactions, banking circulars, withdrawn notices)."""
    from app.models.user import SavedNotification
    from app.models.notification import LifecycleEvent
    from sqlalchemy import or_

    junk_patterns = [
        "%Media Interaction%",
        "%Circulars Withdrawn%",
        "%Draft Notifications/Guidelines%",
        "%Master Circular%",
        "%Master Direction%",
        "%Press Release%",
        "%Monetary Policy%",
        "%RBI Bulletin%",
    ]
    filters = [Notification.title.ilike(p) for p in junk_patterns]
    junk_notifs = db.query(Notification).filter(or_(*filters)).all()
    if not junk_notifs:
        return 0

    junk_ids = [n.id for n in junk_notifs]
    db.query(SavedNotification).filter(SavedNotification.notification_id.in_(junk_ids)).delete(synchronize_session=False)
    db.query(LifecycleEvent).filter(LifecycleEvent.notification_id.in_(junk_ids)).delete(synchronize_session=False)
    count = db.query(Notification).filter(Notification.id.in_(junk_ids)).delete(synchronize_session=False)
    db.commit()
    logger.info(f"Purged {count} non-job/junk notices from database.")
    return count


def sync_sources(db: Session):
    """Ensure configured official sources in DB have current verified URLs and strategies."""
    for src_data in SOURCES:
        org_short = src_data.get("org_short")
        org = db.query(Organization).filter(Organization.short_name == org_short).first()
        if not org:
            continue

        existing_source = db.query(Source).filter(Source.organization_id == org.id).first()
        if existing_source:
            existing_source.name = src_data["name"]
            existing_source.base_url = src_data["base_url"]
            existing_source.recruitment_page_url = src_data["recruitment_page_url"]
            existing_source.parsing_strategy = src_data["parsing_strategy"]
            existing_source.fetch_interval_minutes = src_data["fetch_interval_minutes"]
        else:
            new_source = Source(
                organization_id=org.id,
                category=org.category,
                source_type=SourceType.OFFICIAL_WEBSITE,
                name=src_data["name"],
                base_url=src_data["base_url"],
                recruitment_page_url=src_data["recruitment_page_url"],
                parsing_strategy=src_data["parsing_strategy"],
                fetch_interval_minutes=src_data["fetch_interval_minutes"],
            )
            db.add(new_source)
    db.commit()
    logger.info("Synchronized official source registry with verified portals.")


def seed_verified_notifications(db: Session) -> int:
    """Pre-seed database with real verified notifications if empty."""
    import os
    import json
    from datetime import datetime

    verified_count = db.query(Notification).filter(Notification.is_synthetic == False).count()
    if verified_count > 0:
        logger.info(f"Database already contains {verified_count} verified notifications. Skipping pre-seed.")
        return 0

    json_path = os.path.join(os.path.dirname(__file__), "verified_notifications.json")
    if not os.path.exists(json_path):
        logger.warning(f"Verified notifications seed file not found at {json_path}")
        return 0

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read verified notifications seed file: {e}")
        return 0

    # Build org short_name to id map
    orgs = db.query(Organization).all()
    org_map = {o.short_name: o.id for o in orgs}

    date_fields = [
        'notification_date', 'application_start_date', 'application_end_date',
        'correction_start_date', 'correction_end_date', 'exam_date',
        'admit_card_date', 'result_date', 'age_cutoff_date'
    ]
    datetime_fields = [
        'first_discovered_at', 'last_checked_at', 'last_verified_at', 'updated_at'
    ]

    inserted = 0
    for item in items:
        org_short = item.pop("org_short_name", None)
        org_id = org_map.get(org_short) or item.get("organization_id")
        if not org_id:
            continue

        for fld in date_fields:
            if item.get(fld):
                try:
                    item[fld] = datetime.strptime(str(item[fld])[:10], '%Y-%m-%d').date()
                except Exception:
                    item[fld] = None
        for fld in datetime_fields:
            if item.get(fld):
                try:
                    item[fld] = datetime.fromisoformat(str(item[fld]).replace('Z', ''))
                except Exception:
                    item[fld] = None

        item["organization_id"] = org_id
        item["is_synthetic"] = False
        notif = Notification(**item)
        db.add(notif)
        inserted += 1

    db.commit()
    logger.info(f"Successfully pre-seeded {inserted} verified notifications into database.")
    return inserted


def seed_initial_data(db: Session):
    """Seed organizations, official sources, and verified notifications."""
    existing_orgs = db.query(Organization).count()
    if existing_orgs == 0:
        logger.info("Seeding organizations...")
        org_map = {}
        for org_data in ORGANIZATIONS:
            org = Organization(**org_data)
            db.add(org)
            db.flush()
            org_map[org_data["short_name"]] = org.id
        db.commit()

        for src_data in SOURCES:
            org_short = src_data["org_short"]
            org_id = org_map.get(org_short)
            if not org_id:
                continue
            org = db.query(Organization).filter(Organization.id == org_id).first()
            source = Source(
                organization_id=org_id,
                category=org.category,
                source_type=SourceType.OFFICIAL_WEBSITE,
                name=src_data["name"],
                base_url=src_data["base_url"],
                recruitment_page_url=src_data["recruitment_page_url"],
                parsing_strategy=src_data["parsing_strategy"],
                fetch_interval_minutes=src_data["fetch_interval_minutes"],
            )
            db.add(source)
        db.commit()
        logger.info(f"Seeded {len(ORGANIZATIONS)} organizations and {len(SOURCES)} official sources.")
    else:
        # Sync updated URLs and strategies
        sync_sources(db)

    # Always pre-seed verified notifications if database has none
    seed_verified_notifications(db)

    # Always ensure no synthetic records remain in production database
    purge_synthetic_notifications(db)
    purge_non_job_notifications(db)

