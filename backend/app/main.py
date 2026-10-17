"""ExamRadar India - FastAPI Application"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.database.session import init_db
from app.api.notifications import router as notifications_router
from app.api.profile import router as profile_router
from app.api.sources import router as sources_router

settings = get_settings()

# Logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("examradar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting ExamRadar India backend...")
    init_db()
    logger.info("Database initialized.")

    # Seed data on first run
    from app.services.seed import seed_initial_data
    from app.database.session import SessionLocal
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()

    logger.info("ExamRadar India backend ready.")

    # Automatically start initial background discovery crawl on startup
    if settings.discovery_enabled:
        import threading
        from app.api.sources import _run_discovery_worker
        threading.Thread(target=_run_discovery_worker, daemon=True).start()
        logger.info("Started background discovery thread.")

    yield
    logger.info("Shutting down ExamRadar India backend.")


app = FastAPI(
    title="ExamRadar India",
    description=(
        "API for discovering and managing Indian government recruitment "
        "notifications, examination updates, and eligibility matching."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["*"],  # Dev mode; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(notifications_router)
app.include_router(profile_router)
app.include_router(sources_router)


@app.get("/")
def root():
    return {
        "service": "ExamRadar India",
        "version": "1.0.0",
        "docs": "/docs",
        "api": "/api/v1",
    }
