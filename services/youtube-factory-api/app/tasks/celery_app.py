"""Celery application factory and configuration."""
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "youtube_factory",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.pipeline_tasks",
        "app.tasks.research_tasks",
        "app.tasks.script_tasks",
        "app.tasks.media_tasks",
        "app.tasks.upload_tasks",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task behavior
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Retry defaults
    task_max_retries=3,
    task_default_retry_delay=60,
    # Result expiry
    result_expires=86400,  # 24 hours
    # Concurrency
    worker_concurrency=settings.MAX_CONCURRENT_JOBS,
    # Routing
    task_routes={
        "app.tasks.pipeline_tasks.*": {"queue": "pipeline"},
        "app.tasks.research_tasks.*": {"queue": "research"},
        "app.tasks.script_tasks.*": {"queue": "script"},
        "app.tasks.media_tasks.*": {"queue": "media"},
        "app.tasks.upload_tasks.*": {"queue": "upload"},
    },
    # Queue definitions
    task_queues_max_priority=10,
)

# Signal handlers for job status tracking
@task_prerun.connect
def task_prerun_handler(task_id: str, task, **kwargs) -> None:
    """Mark job as running when task starts."""
    pass  # TODO: Update job status in DB via sync DB call


@task_postrun.connect
def task_postrun_handler(task_id: str, task, retval, state: str, **kwargs) -> None:
    """Mark job as completed/failed based on task outcome."""
    pass  # TODO: Update job status in DB


@task_failure.connect
def task_failure_handler(task_id: str, exception: Exception, **kwargs) -> None:
    """Log task failures and update job status."""
    pass  # TODO: Record error in job, emit log entry
