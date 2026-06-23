"""
services/medicine_reminder_scheduler.py
---------------------------------------
Background scheduler to scan the database for due medicine reminders
and dispatch notifications (Email, Dashboard, Browser) to users.
"""

import os
import logging
from datetime import datetime, timezone, time as dt_time
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Module-level scheduler reference for clean shutdown
_scheduler = None

# Load environment variable for interval
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_backend_dir, ".env"), override=False)
REMINDER_INTERVAL_MINUTES = int(os.getenv("REMINDER_INTERVAL", "1"))

def _is_reminder_due(reminder, current_time, current_weekday: str, now) -> bool:
    """Determine if a reminder should fire right now."""
    if reminder.start_date and now.date() < reminder.start_date:
        return False
    if reminder.end_date and now.date() > reminder.end_date:
        return False
    if reminder.reminder_time is None:
        return False

    r_time = reminder.reminder_time
    if isinstance(r_time, str):
        try:
            parts = r_time.split(":")
            r_time = dt_time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return False

    if r_time.hour != current_time.hour or r_time.minute != current_time.minute:
        return False

    freq = (reminder.frequency or "daily").lower()
    if freq == "daily":
        pass  # Always matches daily
    elif freq in ("weekly", "specific_days"):
        days = (reminder.reminder_days or "").lower()
        if days and current_weekday not in days:
            return False

    # Check if already sent in this specific minute window
    if reminder.last_sent_at:
        last = reminder.last_sent_at
        if (
            last.year == now.year
            and last.month == now.month
            and last.day == now.day
            and last.hour == now.hour
            and last.minute == now.minute
        ):
            return False

    return True

def _check_and_send_reminders(app) -> None:
    """Core job running inside Flask app context to check and dispatch reminders."""
    with app.app_context():
        try:
            from database import db
            from database.models import MedicineReminder, User
            from services.notification_service import send_medicine_reminder_notification

            now = datetime.now(timezone.utc)
            current_time = now.time()
            current_weekday = now.strftime("%A").lower()

            active_reminders = MedicineReminder.query.filter_by(is_active=True).all()
            if not active_reminders:
                return

            sent_count = 0
            for reminder in active_reminders:
                if not _is_reminder_due(reminder, current_time, current_weekday, now):
                    continue

                user = db.session.get(User, reminder.user_id)
                if not user:
                    continue

                # Dispatch notifications via free notification service (Gmail + Dashboard)
                success = send_medicine_reminder_notification(
                    user_id=user.id,
                    medicine_name=reminder.medicine_name,
                    dosage=reminder.dosage,
                    instructions=reminder.instructions
                )

                if success:
                    reminder.last_sent_at = now
                    sent_count += 1
                    logger.info("[Scheduler] Sent reminder #%d to user #%d for '%s'.", reminder.id, user.id, reminder.medicine_name)

            if sent_count > 0:
                db.session.commit()
                logger.info("[Scheduler] Dispatched %d medicine reminder(s) this cycle.", sent_count)

        except Exception as e:
            logger.exception("[Scheduler] Error in reminder check cycle: %s", e)

def start_medicine_reminder_scheduler(app) -> None:
    """Starts the background scheduler daemon."""
    global _scheduler

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.error("[Scheduler] APScheduler not installed. Run: pip install APScheduler")
        return

    if _scheduler is not None:
        logger.warning("[Scheduler] Scheduler already running. Skipping start.")
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        func=_check_and_send_reminders,
        trigger=IntervalTrigger(minutes=REMINDER_INTERVAL_MINUTES),
        args=[app],
        id="medicine_reminder_job",
        name="Medicine Reminder Job",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()

    logger.info("[Scheduler] ✅ Medicine reminder scheduler started (checking every %d min).", REMINDER_INTERVAL_MINUTES)

def stop_medicine_reminder_scheduler() -> None:
    """Stops the background scheduler daemon."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[Scheduler] Medicine reminder scheduler stopped.")
