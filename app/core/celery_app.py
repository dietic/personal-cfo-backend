"""
Celery configuration for Personal CFO background tasks
"""
from celery import Celery
from app.core.config import settings

# Resolve Redis URL from settings (works locally and in Docker)
redis_url = settings.REDIS_URL or "redis://localhost:6379/0"

# Create Celery app
celery_app = Celery(
    "personal_cfo",
    broker=redis_url,
    backend=redis_url,
    include=["app.tasks.statement_tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=480,  # 8 minutes soft limit
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)

# Task routing for different subscription tiers
celery_app.conf.task_routes = {
    'app.tasks.statement_tasks.process_statement_background': {
        'queue': 'statements'
    },
    'app.tasks.statement_tasks.process_statement_premium': {
        'queue': 'priority'  # Future: for premium users
    }
}
