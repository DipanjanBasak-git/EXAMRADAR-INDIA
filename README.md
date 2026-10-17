# ExamRadar India

**ExamRadar India** is a personalized Indian government job and competitive examination notification discovery platform delivered through a Chrome extension and high-performance Python FastAPI backend.

The platform automatically discovers, verifies, organizes, and matches official notifications from central and state recruitment commissions (UPSC, SSC, IBPS, RRB, NTA, State PSCs) against a candidate's educational qualifications, age, and reservation category.

---

## 🌟 Key Features

1. **Official Source Verification & Crawling**
   - Verified crawls from official recruitment portals (`upsc.gov.in`, `ssc.gov.in`, `ibps.in`, `rrbcdg.gov.in`, state PSCs).
   - SSRF-safe URL validation, content hashing, and duplicate detection.
   - Respects robots.txt and rate limits.

2. **Smart Information Extraction**
   - Automatic extraction of advertisement numbers, posts, total vacancies, age limits (min/max), and qualification requirements.
   - Comprehensive multi-format date normalization (`DD/MM/YYYY`, `DD-MM-YYYY`, `DD.MM.YYYY`, `YYYY-MM-DD`, `DD Mon YYYY`).

3. **Personalized Candidate Eligibility Matcher**
   - Exact age calculation with reservation category relaxation rules (General/UR, EWS, OBC 3 yrs, SC/ST 5 yrs, PwBD 10 yrs, Ex-Servicemen).
   - Educational hierarchy matching (10th &rarr; 12th &rarr; Diploma &rarr; Graduate &rarr; Post-Graduate &rarr; Ph.D.).
   - Instant visual tags: **Eligible**, **Closing Soon**, **Applied**, and **Verified**.

4. **Chrome Extension (Manifest V3)**
   - **Popup**: Compact dashboard displaying active openings, personalized matches, closing-soon alerts, category filter, and fast search.
   - **Full Options Dashboard**: Complete candidate profile management, all notifications explorer with advanced sorting, bookmark tracker, official sources status, and manual crawl trigger.
   - **Background Service Worker**: Alarm-based polling, desktop badge counters, and SSRF-safe communications.
   - **Modern Aesthetic**: Glassmorphism touches, harmonious color tokens, dark/light theme toggle, responsive layout, and zero third-party UI framework bloat.

---

## 🏗️ Project Architecture

```
EXAMRADAR INDIA/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI REST endpoints
│   │   │   ├── notifications.py  # Notification browse, filter, dashboard, bookmarking
│   │   │   ├── profile.py        # Candidate profile, qualifications, alert settings
│   │   │   └── sources.py        # Source status, manual crawl trigger
│   │   ├── core/            # Configuration & Settings (Pydantic v2)
│   │   ├── database/        # SQLite / PostgreSQL engine & session setup
│   │   ├── models/          # SQLAlchemy ORM models (Notifications, Sources, Users)
│   │   ├── schemas/         # Pydantic data schemas
│   │   ├── services/        # Business logic:
│   │   │   ├── discovery.py      # Crawler, HTML/PDF extractor, SSRF guard
│   │   │   ├── eligibility.py    # Age & qualification rules engine
│   │   │   ├── notifications.py  # Status calculators & aggregators
│   │   │   └── seed.py           # Preloaded official sources & sample notifications
│   │   ├── workers/         # APScheduler periodic discovery process
│   │   └── main.py          # Application entrypoint & lifespan lifecycle
│   ├── tests/
│   │   └── test_examradar.py  # 51 unit & integration tests
│   └── requirements.txt
├── extension/
│   ├── icons/               # 16x16, 32x32, 48x48, 128x128 extension icons
│   ├── manifest.json        # Chrome Extension Manifest V3
│   ├── background.js        # Background service worker
│   ├── api.js               # Extension API client
│   ├── popup.html / popup.js # Compact popup window controller
│   ├── dashboard.html / dashboard.js # Full dashboard & options page
│   └── styles.css           # Complete design system & dark mode CSS
├── .env.example
├── run_backend.bat
└── README.md
```

---

## 🚀 Quickstart Guide

### 1. Start the Backend API

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Install dependencies (if not already installed):
   ```bash
   pip install -r requirements.txt
   ```
3. Start the FastAPI development server:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
4. Verify the backend is running:
   - Interactive Swagger API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

*(On first startup, the application automatically initializes the database and seeds 16 recruitment organizations, 10 official sources, and 8 realistic test notifications).*

---

### 2. Install the Chrome Extension

1. Open Google Chrome and go to `chrome://extensions/`.
2. Enable **Developer mode** using the toggle switch in the top-right corner.
3. Click the **Load unpacked** button.
4. Select the `extension/` folder inside this repository:
   ```
   c:\Users\Dipanjan\OneDrive\Desktop\EXAMRADAR INDIA\extension
   ```
5. The **ExamRadar India** icon will appear in your Chrome toolbar.
6. Click the extension icon to view the popup, or right-click &rarr; **Options** (or click the Dashboard icon in the popup header) to open the full dashboard.

---

### 3. Run Backend Test Suite

To verify all 51 automated tests (eligibility calculation, date parsing, SSRF guard, age relaxation, API endpoints):
```bash
python -m pytest backend/tests/test_examradar.py -v
```

---

## 🛡️ Security & Privacy Guardrails

- **Zero Untrusted Scraping**: Strictly restricted to pre-approved government commission domains (`.gov.in`, `.nic.in`, `.ac.in`, `.org`, `.in`).
- **SSRF Prevention**: IP address resolution validation blocks loopback (`127.0.0.1`), private RFC1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), and metadata service addresses.
- **Minimal Browser Permissions**: Uses only `storage`, `alarms`, and `notifications`. No broad browser history or tab capturing.
