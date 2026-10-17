"""ExamRadar India - Source & Organization Models"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Enum, JSON, Float, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database.session import Base


class SourceType(str, enum.Enum):
    OFFICIAL_WEBSITE = "official_website"
    RSS_FEED = "rss_feed"
    OFFICIAL_API = "official_api"
    PDF_LISTING = "pdf_listing"


class RecruitmentCategory(str, enum.Enum):
    BANKING = "banking"
    UPSC = "upsc"
    SSC = "ssc"
    RAILWAYS = "railways"
    DEFENCE = "defence"
    CENTRAL_GOVT = "central_govt"
    STATE_GOVT = "state_govt"
    PSU = "psu"
    TEACHING = "teaching"
    POLICE = "police"
    RESEARCH = "research"
    OTHER = "other"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False)
    short_name = Column(String(100), nullable=True)
    official_website = Column(String(1000), nullable=True)
    category = Column(Enum(RecruitmentCategory), nullable=False)
    description = Column(Text, nullable=True)
    logo_url = Column(String(1000), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sources = relationship("Source", back_populates="organization")
    notifications = relationship("Notification", back_populates="organization")


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False)
    base_url = Column(String(2000), nullable=False)
    recruitment_page_url = Column(String(2000), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    category = Column(Enum(RecruitmentCategory), nullable=False)
    source_type = Column(Enum(SourceType), default=SourceType.OFFICIAL_WEBSITE)
    is_enabled = Column(Boolean, default=True)
    fetch_interval_minutes = Column(Integer, default=360)  # 6 hours
    last_successful_check = Column(DateTime, nullable=True)
    last_discovered_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    error_count = Column(Integer, default=0)
    parsing_strategy = Column(String(200), default="generic_html")
    config = Column(JSON, nullable=True)  # Source-specific config
    robots_txt_checked = Column(Boolean, default=False)
    robots_txt_allowed = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="sources")
    discovery_logs = relationship("DiscoveryLog", back_populates="source")
