"""ExamRadar India - Pydantic Schemas for Sources"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class SourceSchema(BaseModel):
    id: int
    name: str
    base_url: str
    recruitment_page_url: Optional[str] = None
    organization_id: int
    organization_name: Optional[str] = None
    category: str
    source_type: str
    is_enabled: bool = True
    fetch_interval_minutes: int = 360
    last_successful_check: Optional[datetime] = None
    last_discovered_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    error_count: int = 0
    notifications_count: int = 0
    parsing_strategy: str = "generic_html"
    robots_txt_allowed: bool = True

    model_config = ConfigDict(from_attributes=True)


class SourceStatusResponse(BaseModel):
    total_sources: int = 0
    enabled_sources: int = 0
    sources_with_errors: int = 0
    last_discovery_run: Optional[datetime] = None
    sources: list[SourceSchema] = []


class DiscoveryStatusResponse(BaseModel):
    is_running: bool = False
    last_run: Optional[datetime] = None
    next_scheduled_run: Optional[datetime] = None
    total_sources_checked: int = 0
    total_notifications_found: int = 0
    errors: list[str] = []


class OrganizationSchema(BaseModel):
    id: int
    name: str
    short_name: Optional[str] = None
    official_website: Optional[str] = None
    category: str
    description: Optional[str] = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)
