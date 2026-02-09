"""
Scheduler Service - Runs the calling cycle every 10 minutes.
Picks the next eligible lead and initiates exactly ONE call per cycle.
"""
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import settings

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.last_run_at = None
        self.call_in_progress = False
        self._db = None
        self._process_lead_callback = None

    def configure(self, db, process_lead_callback):
        """Configure scheduler with database and callback."""
        self._db = db
        self._process_lead_callback = process_lead_callback

    async def _run_cycle(self):
        """Execute one calling cycle."""
        if self.call_in_progress:
            logger.info("Scheduler: Call already in progress. Skipping this cycle.")
            return

        self.last_run_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"Scheduler cycle started at {self.last_run_at}")

        try:
            if self._process_lead_callback:
                await self._process_lead_callback()
            else:
                logger.warning("No process_lead_callback configured")
        except Exception as e:
            logger.error(f"Scheduler cycle error: {e}")
        finally:
            # Log the cycle
            if self._db:
                await self._db.scheduler_logs.insert_one({
                    "timestamp": self.last_run_at,
                    "status": "completed",
                    "call_in_progress": self.call_in_progress
                })

    def start(self):
        """Start the scheduler."""
        if self.is_running:
            logger.info("Scheduler already running")
            return

        interval = settings.SCHEDULER_INTERVAL_MINUTES
        self.scheduler.add_job(
            self._run_cycle,
            'interval',
            minutes=interval,
            id='calling_cycle',
            replace_existing=True
        )
        self.scheduler.start()
        self.is_running = True
        logger.info(f"Scheduler started: running every {interval} minutes")

    def stop(self):
        """Stop the scheduler."""
        if not self.is_running:
            logger.info("Scheduler already stopped")
            return

        self.scheduler.shutdown(wait=False)
        self.is_running = False
        logger.info("Scheduler stopped")

    async def trigger_now(self):
        """Manually trigger a cycle immediately."""
        logger.info("Manual trigger: running cycle now")
        await self._run_cycle()

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "is_running": self.is_running,
            "last_run_at": self.last_run_at,
            "call_in_progress": self.call_in_progress,
            "interval_minutes": settings.SCHEDULER_INTERVAL_MINUTES
        }


scheduler_service = SchedulerService()
