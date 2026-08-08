import os

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

celery = Celery(
    "tasks",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
)

celery.conf.timezone = "Asia/Kolkata"
celery.conf.beat_schedule = {
    "daily-deadline-reminders": {
        "task": "tasks.send_daily_deadline_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    "monthly-admin-report": {
        "task": "tasks.send_monthly_admin_report",
        "schedule": crontab(day_of_month=1, hour=8, minute=0),
    },
}
