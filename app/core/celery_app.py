from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "personalcfo",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.statement_tasks", "app.tasks.notification_tasks", "app.tasks.income_tasks"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_routes={
        "app.tasks.statement_tasks.*": {"queue": "statements"},
        "app.tasks.notification_tasks.*": {"queue": "priority"},
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=50,
    beat_schedule={
        "process-recurring-incomes": {
            "task": "app.tasks.income_tasks.process_recurring_incomes_task",
            "schedule": crontab(minute=5, hour=0),  # Run daily at 00:05 Peru time (05:05 UTC)
            "options": {"queue": "default"},
        },
    },
)

if __name__ == "__main__":
    celery_app.start()
