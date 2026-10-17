"""ExamRadar India - Discovery Worker

Runs the discovery engine on a schedule using APScheduler.
Can be run as a separate process or integrated with the backend.
"""

import logging
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import SessionLocal, init_db
from app.services.discovery import DiscoveryEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("examradar.worker")


def run_discovery_job():
    """Execute a discovery run across all enabled sources."""
    logger.info("Starting scheduled discovery run...")
    db = SessionLocal()
    try:
        engine = DiscoveryEngine(db)
        try:
            results = engine.run_discovery()
            total_new = sum(r.get("new", 0) for r in results)
            total_errors = sum(1 for r in results if r.get("status") == "error")
            logger.info(
                f"Discovery run complete: {len(results)} sources checked, "
                f"{total_new} new notifications, {total_errors} errors."
            )
            for r in results:
                if r.get("status") == "error":
                    logger.warning(
                        f"  Source '{r['source_name']}': {r.get('error', 'Unknown error')}"
                    )
        finally:
            engine.close()
    except Exception as e:
        logger.exception(f"Discovery run failed: {e}")
    finally:
        db.close()


def main():
    """Start the discovery worker."""
    settings = get_settings()

    if not settings.discovery_enabled:
        logger.info("Discovery is disabled. Exiting.")
        sys.exit(0)

    # Initialize database
    init_db()

    interval = settings.discovery_interval_minutes
    logger.info(f"Starting discovery worker. Interval: {interval} minutes.")

    # Run once immediately
    run_discovery_job()

    # Schedule recurring runs
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_discovery_job,
        "interval",
        minutes=interval,
        id="discovery_job",
        name="Periodic Discovery Run",
        max_instances=1,
        coalesce=True,
    )

    try:
        logger.info("Discovery worker scheduler started. Press Ctrl+C to stop.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Discovery worker shutting down.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
