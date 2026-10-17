"""ExamRadar India - Discovery Engine

Manages the source registry, scheduled discovery, and notification extraction.
"""

import hashlib
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional
from urllib.parse import urlparse, urljoin

import ssl
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models.source import Source, Organization, RecruitmentCategory, SourceType
from app.models.notification import (
    Notification, ApplicationStatus, VerificationStatus, DiscoveryLog, LifecycleEvent
)

logger = logging.getLogger("examradar.discovery")

# SSRF protection: block private/reserved networks
BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254",  # cloud metadata
    "metadata.google.internal",
}
BLOCKED_PREFIXES = ["10.", "172.16.", "172.17.", "172.18.", "172.19.",
                     "172.20.", "172.21.", "172.22.", "172.23.",
                     "172.24.", "172.25.", "172.26.", "172.27.",
                     "172.28.", "172.29.", "172.30.", "172.31.",
                     "192.168."]


def is_safe_url(url: str) -> bool:
    """Check URL is safe (not pointing to internal/private networks)."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        if host in BLOCKED_HOSTS:
            return False
        for prefix in BLOCKED_PREFIXES:
            if host.startswith(prefix):
                return False
        if parsed.scheme not in ("http", "https"):
            return False
        return True
    except Exception:
        return False


def content_hash(text: str) -> str:
    """Generate a SHA-256 hash of content for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_date(date_str: str) -> Optional[date]:
    """Try to parse various Indian date formats."""
    if not date_str:
        return None
    date_str = date_str.strip()
    # Common formats
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%d %b %Y", "%d %B %Y",
        "%B %d, %Y", "%b %d, %Y",
        "%d/%m/%y", "%d-%m-%y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def extract_dates_from_text(text: str) -> dict:
    """Extract key dates (start, deadline, exam, notification date) from notification text."""
    dates = {}
    text_lower = text.lower()

    # 1. Date ranges (e.g., "from 30.09.2026 to 21.10.2026" or "15-01-2026 to 15-02-2026")
    range_match = re.search(
        r"(?:apply\s+(?:online\s+)?from\s+|from\s+)?(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\s*(?:to|-)\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
        text_lower
    )
    if range_match:
        start_d = normalize_date(range_match.group(1))
        end_d = normalize_date(range_match.group(2))
        if start_d:
            dates["application_start_date"] = start_d
        if end_d:
            dates["application_end_date"] = end_d

    # 2. Specific date patterns
    patterns = {
        "application_start_date": [
            r"(?:start(?:ing)?|open(?:ing)?|commence)\s*(?:date|from)?\s*[:.-]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
            r"(?:apply\s+from|applications?\s+(?:start|open))\s*[:.-]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
        ],
        "application_end_date": [
            r"(?:last\s+date(?:\s+to\s+apply)?|closing\s+date|end\s+date|deadline)\s*[:.-]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
            r"(?:apply\s+(?:before|by|till))\s*[:.-]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
        ],
        "exam_date": [
            r"(?:exam(?:ination)?\s+date)\s*[:.-]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
            r"(?:date\s+of\s+(?:written\s+)?exam(?:ination)?)\s*[:.-]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
        ],
        "notification_date": [
            r"(?:date(?:\s+of\s+issue|\s+of\s+notification)?|dated)\s*[:.-]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
            r"\b([a-z]{3,9}\s+\d{1,2},?\s+\d{4})\b",
            r"\b(\d{1,2}\s+[a-z]{3,9},?\s+\d{4})\b",
        ],
    }

    for field, pats in patterns.items():
        if field in dates:
            continue
        for pat in pats:
            match = re.search(pat, text_lower)
            if match:
                parsed = normalize_date(match.group(1))
                if parsed:
                    dates[field] = parsed
                    break
    return dates


def extract_vacancies(text: str) -> Optional[int]:
    """Extract total number of vacancies safely, preventing years from being counted as vacancies."""
    text_lower = text.lower()
    patterns = [
        r"(?:total\s+)?(?:no\.?\s+of\s+)?vacanc(?:y|ies)\s*[:.-]?\s*(\d+)",
        r"(\d+)\s+vacanc(?:y|ies)",
        r"(?:total\s+)?(?:no\.?\s+of\s+)?posts?\s*[:.-]?\s*(\d+)",
        r"(\d+)\s+posts?\b",
    ]
    for pat in patterns:
        match = re.search(pat, text_lower)
        if match:
            try:
                num = int(match.group(1))
                # Protect against calendar years (e.g. 1950-2040) being mistaken for vacancy counts
                if 1950 <= num <= 2040:
                    if any(w in text_lower for w in ["year", "since", "dated", "circular", "batch", "class", "ad", "advt"]):
                        continue
                    if "vacanc" not in match.group(0):
                        continue
                if 1 <= num <= 500000:
                    return num
            except ValueError:
                continue
    return None


def extract_age_limits(text: str) -> tuple[Optional[int], Optional[int]]:
    """Extract age limits from text."""
    patterns = [
        r"age\s*(?:limit)?\s*[:.-]?\s*(\d{1,2})\s*(?:to|-)\s*(\d{1,2})\s*years?",
        r"(?:minimum|min)\s*age\s*[:.-]?\s*(\d{1,2}).*?(?:maximum|max)\s*age\s*[:.-]?\s*(\d{1,2})",
    ]
    for pat in patterns:
        match = re.search(pat, text.lower())
        if match:
            try:
                return int(match.group(1)), int(match.group(2))
            except ValueError:
                continue
    return None, None


class DiscoveryEngine:
    """Discovers recruitment notifications from configured official government sources."""

    def __init__(self, db: Session, timeout: int = 30):
        self.db = db
        self.timeout = timeout

        # Configure SSL context supporting legacy Indian government TLS ciphers
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)

        self.client = httpx.Client(
            verify=ctx,
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 ExamRadar/1.0"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
            },
        )

    def close(self):
        self.client.close()

    def check_source(self, source: Source) -> DiscoveryLog:
        """Check a single source for new notifications."""
        log = DiscoveryLog(
            source_id=source.id,
            started_at=datetime.utcnow(),
            status="started",
        )

        url = source.recruitment_page_url or source.base_url
        if not is_safe_url(url):
            log.status = "error"
            log.error_message = f"URL blocked by SSRF protection: {url}"
            log.completed_at = datetime.utcnow()
            source.last_error = log.error_message
            source.last_error_at = datetime.utcnow()
            source.error_count += 1
            logger.warning(f"Source '{source.name}' ({url}) -> SSRF blocked.")
            self.db.add(log)
            self.db.commit()
            return log

        try:
            response = self.client.get(url)
            response.raise_for_status()

            # Check for bot challenge / CAPTCHA redirection
            final_url_str = str(response.url).lower()
            resp_lower = response.text.lower()
            if "authentication.aspx" in final_url_str or ("captcha" in resp_lower and len(response.text) < 15000) or "please enable javascript to view" in resp_lower:
                log.status = "error"
                log.error_message = "Protected by bot verification/CAPTCHA challenge (automated scraping unavailable)"
                log.completed_at = datetime.utcnow()
                source.last_error = log.error_message
                source.last_error_at = datetime.utcnow()
                source.error_count += 1
                logger.warning(f"Source '{source.name}' ({url}) -> HTTP {response.status_code} [CAPTCHA/WAF Protected]")
                self.db.add(log)
                self.db.commit()
                return log

            soup = BeautifulSoup(response.text, "html.parser")
            links = self._extract_notification_links(soup, str(response.url), source)
            log.notifications_found = len(links)

            new_count = 0
            updated_count = 0

            for link_info in links:
                result = self._process_link(link_info, source)
                if result == "new":
                    new_count += 1
                elif result == "updated":
                    updated_count += 1

            log.notifications_new = new_count
            log.notifications_updated = updated_count
            log.status = "success"
            log.completed_at = datetime.utcnow()

            source.last_successful_check = datetime.utcnow()
            if new_count > 0:
                source.last_discovered_at = datetime.utcnow()
            source.error_count = 0
            source.last_error = None

            logger.info(
                f"Source '{source.name}' ({url}) -> HTTP {response.status_code} | "
                f"Found {len(links)} candidate links, {new_count} new verified, {updated_count} updated."
            )

        except httpx.HTTPStatusError as e:
            log.status = "error"
            log.error_message = f"HTTP {e.response.status_code}: {str(e)[:500]}"
            log.completed_at = datetime.utcnow()
            source.last_error = log.error_message
            source.last_error_at = datetime.utcnow()
            source.error_count += 1
            logger.warning(f"Source '{source.name}' ({url}) -> FAILED: HTTP {e.response.status_code}")

        except httpx.RequestError as e:
            log.status = "error"
            log.error_message = f"Request failed: {str(e)[:500]}"
            log.completed_at = datetime.utcnow()
            source.last_error = log.error_message
            source.last_error_at = datetime.utcnow()
            source.error_count += 1
            logger.warning(f"Source '{source.name}' ({url}) -> FAILED: {str(e)[:200]}")

        except Exception as e:
            log.status = "error"
            log.error_message = f"Unexpected error: {str(e)[:500]}"
            log.completed_at = datetime.utcnow()
            source.last_error = log.error_message
            source.last_error_at = datetime.utcnow()
            source.error_count += 1
            logger.exception(f"Source '{source.name}' ({url}) -> Exception: {e}")

        self.db.add(log)
        self.db.commit()
        return log

    def _extract_notification_links(
        self, soup: BeautifulSoup, base_url: str, source: Source
    ) -> list[dict]:
        """Extract genuine notification links based on source parsing strategy."""
        links = []
        seen_urls = set()
        strategy = source.parsing_strategy or "generic_html"

        keywords = [
            "recruit", "vacancy", "notification", "advertisement", "advt",
            "examination", "cbt", "post", "officer", "clerk", "associate",
            "scientist", "engineer", "corrigendum", "extension", "special notice",
            "selection", "admit", "result", "interview", "schedule", "syllabus",
        ]
        skip_kw = [
            "privacy", "terms", "sitemap", "contact", "about", "feedback",
            "disclaimer", "skip to", "screen reader", "login", "register",
            "forgot", "faq", "copyright", "rti", "tenders", "gallery",
        ]

        generic_navigation_titles = {
            "active examinations", "forthcoming examinations", "previous question papers",
            "cut-off marks", "answer keys", "marks of recommended candidates",
            "marks of recommended candidates (reserve list)", "specimen question cum answer booklet (qcab)",
            "common mistakes committed by the candidates in conventional papers",
            "revised syllabus and scheme", "representation on question papers",
            "demo files", "online recruitment application (ora)", "recruitment tests",
            "recruitment requisition", "recruitment cases kept on hold on account of pending litigations",
            "interview / pt", "download call letter (for interview/ personality test)",
            "download call letter", "apply online", "view all", "click here", "read more",
            "all notifications", "archived notifications", "examination calendar",
            "syllabus", "scheme of examination", "forms and downloads", "tenders",
            "contact us", "faq", "faqs", "helpdesk", "user manual",
            "join sbi", "current openings", "recruitment results", "recruitment results & archive",
            "what are you looking for", "direct recruitment", "application (special notice)",
            "city intimation (exam)", "document verification", "e-call letters", "exam results",
            "selection list", "provisional panel", "cbt scorecard"
        }

        def add_link(full_url: str, text: str, context_text: str = "", apply_url: Optional[str] = None):
            clean_txt = " ".join(text.split())
            if not clean_txt or len(clean_txt) < 12:
                return
            clean_lower = clean_txt.lower().strip()
            if clean_lower in generic_navigation_titles or clean_lower.rstrip(":") in generic_navigation_titles:
                return
            if any(clean_lower == g for g in generic_navigation_titles):
                return
            # Strict non-job filter to avoid banking regulations, media notices, and circulars
            if any(nj in clean_lower for nj in [
                "media interaction", "circulars withdrawn", "draft notifications/guidelines",
                "master circular", "master direction", "monetary policy", "speech by",
                "press release", "tender notice", "auction of", "holiday list", "faqs on",
                "holidays", "terms and conditions", "privacy policy"
            ]):
                return
            if full_url in seen_urls:
                return
            if not is_safe_url(full_url):
                return
            clean_full = full_url.split("?")[0].rstrip("/")
            clean_base = base_url.split("?")[0].rstrip("/")
            if clean_full == clean_base:
                return
            seen_urls.add(full_url)
            links.append({
                "url": full_url,
                "text": clean_txt[:500],
                "context_text": (context_text or clean_txt)[:3000],
                "apply_url": apply_url,
                "source_id": source.id,
                "category": source.category.value,
                "organization_id": source.organization_id,
            })

        # Dedicated parser for SBI Careers structured cards
        if strategy == "sbi_html":
            for card in soup.select("div.card"):
                card_text = " ".join(card.get_text().split())
                pdf_link = card.find("a", href=lambda h: h and (".pdf" in h.lower() or "advertisement" in h.lower()))
                apply_link = card.find("a", href=lambda h: h and "apply" in h.lower())
                target_a = pdf_link or apply_link
                if not target_a:
                    continue
                apply_url = urljoin(base_url, apply_link["href"]) if apply_link and apply_link.get("href") else None
                title_clean = card_text
                for marker in ["ADVERTISEMENT NO", "LAST DATE TO APPLY", "DOWNLOAD ADVERTISEMENT", "English ("]:
                    if marker in title_clean:
                        title_clean = title_clean.split(marker)[0].strip()
                if len(title_clean) > 15:
                    add_link(
                        urljoin(base_url, target_a["href"]),
                        title_clean[:300],
                        context_text=card_text,
                        apply_url=apply_url
                    )
            return links[:40]

        # Dedicated parser for RBI Opportunities vacancies portal
        if strategy == "rbi_html":
            for tr in soup.find_all("tr"):
                a_tag = tr.find("a", href=lambda h: h and ("id=" in h.lower() or ".pdf" in h.lower() or "vacanc" in h.lower()))
                if not a_tag:
                    continue
                href = a_tag.get("href", "").strip()
                title_text = a_tag.get_text(strip=True)
                if len(title_text) < 12:
                    continue
                row_text = " ".join(tr.get_text().split())
                add_link(urljoin(base_url, href), title_text, context_text=row_text)
            return links[:40]

        # Dedicated parser for DRDO RAC structured advertisement cards
        if strategy == "drdo_html":
            for card in soup.select("div.shadowTop, div.GiDiv03"):
                card_text = " ".join(card.get_text().split())
                pdf_link = card.find("a", href=lambda h: h and ("advt" in h.lower() or ".pdf" in h.lower()))
                if not pdf_link:
                    continue
                title_clean = card_text
                for marker in ["Check latest updates", "Brief Advertisement", "Frequently Asked Questions", "Tentative Schedule"]:
                    if marker in title_clean:
                        title_clean = title_clean.split(marker)[0].strip()
                if len(title_clean) > 15:
                    add_link(urljoin(base_url, pdf_link["href"]), title_clean[:300], context_text=card_text)
            for a_tag in soup.find_all("a", href=True):
                txt = a_tag.get_text(strip=True)
                if any(k in txt.lower() for k in ["addendum to advt", "public notice", "recruitment of"]):
                    add_link(urljoin(base_url, a_tag["href"]), txt)
            return links[:40]

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.lower().startswith(("javascript:", "#", "mailto:", "tel:")):
                continue

            text = a_tag.get_text(strip=True)
            context_text = text
            parent_row = a_tag.find_parent(["tr", "li", "div", "p"])
            if parent_row:
                context_text = " ".join(parent_row.get_text().split())
                if len(text) < 15 or text.lower() in ["download", "notice", "view", "details", "click here", "pdf"]:
                    text = context_text

            combined = (href + " " + text).lower()

            if any(s in combined for s in skip_kw):
                continue

            is_relevant = False
            if strategy == "upsc_html":
                # Only include actual notification/results/exam links, avoid navigation bars
                if href.rstrip("/").endswith(("/active-exams", "/forthcoming-exams", "/previous-question-papers", "/cutoff-marks--", "/answer-key", "/recruitment-test", "/recruitment-requisition")):
                    continue
                is_relevant = any(k in combined for k in [
                    "posts of", "recruitment to", "notice:", "result:", "advt",
                    "interview schedule", "provisional answer key", "written result"
                ]) or ("/whats-new/" in href)
            elif strategy == "wbpsc_html":
                if any(bad in href.lower() for bad in ["interview_pt.jsp", "callletter.jsp", "contactus.jsp"]):
                    continue
                is_relevant = "param1=" in href or any(k in combined for k in [
                    "advertisement", "recruitment", "scheme", "syllabus", "vacancy"
                ])
            elif strategy == "isro_html":
                is_relevant = any(k in combined for k in ["advt", "recruitment", "scientist", "engineer", "icrb"])
            elif strategy == "rrb_html":
                is_cen_notice = bool(re.search(r"\((?:RPF|CEN|\d{2}/\d{4})\)", text, re.IGNORECASE))
                is_relevant = is_cen_notice or any(k in combined for k in ["special notice on examination", "cbt exam schedule"])
            elif strategy == "ibps_html":
                if href.rstrip("/").endswith(("/clerical-cadre", "/specialist-officers", "/probationary-officers", "/careers", "/regional-rural-banks")):
                    continue
                is_relevant = any(k in combined for k in ["crp", "recruitment", "notification", "specialist", "po/mt", "ciso", "registration"])
            else:
                is_relevant = any(kw in combined for kw in keywords)

            if is_relevant:
                full_url = urljoin(base_url, href)
                add_link(full_url, text, context_text=context_text)

        return links[:40]

    def _process_link(self, link_info: dict, source: Source) -> str:
        """Process a single discovered link. Returns 'new', 'updated', or 'skip'."""
        url = link_info["url"]
        title = link_info.get("text", "")
        if not title or len(title) < 10:
            return "skip"

        title = " ".join(title.split())
        title_lower = title.lower()

        # Reject obvious non-recruitment items
        if any(nj in title_lower for nj in [
            "media interaction", "circulars withdrawn", "draft notifications/guidelines",
            "master circular", "master direction", "monetary policy", "speech by",
            "press release", "tender notice", "auction of", "holiday list", "faqs on",
            "rbi bulletin", "minutes of", "annual report"
        ]):
            return "skip"

        # Check for Corrigendum / Extension targeting an existing recruitment
        is_corrigendum = any(k in title_lower for k in [
            "corrigendum", "extension", "last date extended", "addendum", "revised date"
        ])

        if is_corrigendum:
            existing = self.db.query(Notification).filter(
                Notification.organization_id == link_info["organization_id"],
                Notification.is_active == True,
            ).order_by(Notification.first_discovered_at.desc()).first()

            if existing:
                already_recorded = any(
                    title_lower in (ev.description or "").lower()
                    for ev in existing.lifecycle_events
                ) if existing.lifecycle_events else False

                if not already_recorded:
                    extended_date = None
                    date_match = re.search(r"\b(\d{1,2}[-./]\d{1,2}[-./]\d{2,4})\b", title)
                    if date_match:
                        extended_date = normalize_date(date_match.group(1))

                    event = LifecycleEvent(
                        notification_id=existing.id,
                        event_type="deadline_extended" if extended_date else "corrigendum",
                        event_date=datetime.combine(extended_date, datetime.min.time()) if extended_date else datetime.utcnow(),
                        description=title,
                        source_url=url,
                        verified=True,
                    )
                    existing.lifecycle_events.append(event)
                    if extended_date and (not existing.application_end_date or extended_date > existing.application_end_date):
                        existing.application_end_date = extended_date

                    existing.last_verified_at = datetime.utcnow()
                    self.db.commit()
                    return "updated"

        # Check if already stored
        existing = self.db.query(Notification).filter(
            (Notification.official_notification_url == url) |
            (Notification.source_url == url)
        ).first()

        if existing:
            return "skip"

        existing_title = self.db.query(Notification).filter(
            Notification.organization_id == link_info["organization_id"],
            Notification.title == title,
        ).first()

        if existing_title:
            return "skip"

        # Extract dates, advt number, and vacancies from context or card text
        context = link_info.get("context_text", "") or title
        context_dates = extract_dates_from_text(context)
        context_vacancies = extract_vacancies(context)
        context_min_age, context_max_age = extract_age_limits(context)

        # Extract advertisement number via regex
        advt_no = None
        advt_match = re.search(
            r"(?:Advt\.?\s*No\.?|Advertisement\s*No\.?|CRPD\/[A-Za-z0-9\/\-_]+|CEN\s*No\.?|CEN|Notice\s*No\.?|CRP[- ][A-Za-z0-9\/\-_]+)\s*[:\s]*([A-Za-z0-9\/\-_().]+)",
            context, re.IGNORECASE
        )
        if advt_match:
            advt_no = advt_match.group(0).strip()

        # Date in title or row text
        notif_date = context_dates.get("notification_date")
        if not notif_date:
            date_match = re.search(r"\b([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}[-./]\d{1,2}[-./]\d{2,4})\b", context)
            if date_match:
                notif_date = normalize_date(date_match.group(1))

        # Create genuine notification record
        notification = Notification(
            title=title,
            organization_id=link_info["organization_id"],
            category=link_info["category"],
            advertisement_number=advt_no,
            total_vacancies=context_vacancies,
            min_age=context_min_age,
            max_age=context_max_age,
            notification_date=notif_date,
            application_start_date=context_dates.get("application_start_date"),
            application_end_date=context_dates.get("application_end_date"),
            exam_date=context_dates.get("exam_date"),
            official_notification_url=url,
            official_application_url=link_info.get("apply_url"),
            source_url=source.recruitment_page_url or source.base_url,
            source_domain=urlparse(url).netloc,
            application_status=ApplicationStatus.APPLICATION_OPEN,
            verification_status=VerificationStatus.OFFICIAL_VERIFIED,
            extraction_method=f"official_{source.parsing_strategy}",
            first_discovered_at=datetime.utcnow(),
            last_checked_at=datetime.utcnow(),
            last_verified_at=datetime.utcnow(),
            is_synthetic=False,
            is_active=True,
        )

        try:
            if is_safe_url(url) and not url.lower().endswith((".pdf", ".zip", ".doc", ".docx")):
                resp = self.client.get(url, timeout=5.0)
                if resp.status_code == 200:
                    detail_soup = BeautifulSoup(resp.text, "html.parser")
                    page_text = detail_soup.get_text(separator="\n", strip=True)
                    notification.raw_text = page_text[:10000]
                    notification.content_hash = content_hash(page_text)

                    dates = extract_dates_from_text(page_text)
                    if not notification.application_start_date and "application_start_date" in dates:
                        notification.application_start_date = dates["application_start_date"]
                    if not notification.application_end_date and "application_end_date" in dates:
                        notification.application_end_date = dates["application_end_date"]
                    if not notification.exam_date and "exam_date" in dates:
                        notification.exam_date = dates["exam_date"]

                    vacancies = extract_vacancies(page_text)
                    if not notification.total_vacancies and vacancies:
                        notification.total_vacancies = vacancies

                    min_age, max_age = extract_age_limits(page_text)
                    if not notification.min_age and min_age:
                        notification.min_age = min_age
                    if not notification.max_age and max_age:
                        notification.max_age = max_age
        except Exception:
            pass

        self.db.add(notification)
        self.db.commit()
        return "new"

    def run_discovery(self, source_ids: list[int] = None, force: bool = False):
        """Run discovery for all enabled sources or specified sources."""
        query = self.db.query(Source).filter(Source.is_enabled == True)
        if source_ids:
            query = query.filter(Source.id.in_(source_ids))

        sources = query.all()
        results = []

        for source in sources:
            if source.last_successful_check and not force and not source_ids:
                next_check = source.last_successful_check + timedelta(
                    minutes=source.fetch_interval_minutes
                )
                if datetime.utcnow() < next_check:
                    continue

            log = self.check_source(source)
            results.append({
                "source_id": source.id,
                "source_name": source.name,
                "status": log.status,
                "found": log.notifications_found,
                "new": log.notifications_new,
                "updated": log.notifications_updated,
                "error": log.error_message,
            })

        return results

