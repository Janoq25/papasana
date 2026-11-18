from celery import Celery

from app.core.config import get_settings

_s = get_settings()

celery_app = Celery("papasana", broker=_s.redis_url, backend=_s.redis_url, include=["app.workers.tasks"])
celery_app.conf.update(
    timezone=_s.tz_display,
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
)
