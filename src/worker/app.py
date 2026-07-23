import os
from typing import Any, Optional

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown
from kombu import Queue

app = Celery("bunkerweb", include=["worker.tasks"])

app.conf.update(
    broker_url=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    broker_pool_limit=4,
    broker_transport_options={
        "visibility_timeout": 7200,
        "max_connections": 8,
    },
    broker_connection_retry_on_startup=True,
    result_backend=None,
    task_serializer="json",
    result_serializer="json",
    event_serializer="json",
    accept_content=["json"],
    result_accept_content=["json"],
    task_acks_late=False,
    task_reject_on_worker_lost=False,
    task_track_started=True,
    task_time_limit=1800,
    task_soft_time_limit=900,
    worker_max_tasks_per_child=1,
    worker_max_memory_per_child=300000,
    worker_prefetch_multiplier=1,
    worker_soft_shutdown_timeout=900.0,
    worker_hijack_root_logger=False,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_queues=[
        Queue("default"),
        Queue("heavy"),
    ],
    task_default_queue="default",
    timezone="UTC",
    enable_utc=True,
)

HEAVY_JOBS = {
    "backup-data",
    "bunkernet-data",
    "bunkernet-register",
    "certbot-auth",
    "certbot-cleanup",
    "certbot-new",
    "certbot-renew",
    "coreruleset-nightly",
    "download-crs-plugins",
    "download-plugins",
    "download-pro-plugins",
    "push-configs",
}


def route_job(name: str, args: tuple[Any, ...], kwargs: dict[str, Any], options: dict[str, Any], task=None, **kw) -> dict[str, str]:
    job_data = args[0] if args else kwargs.get("job_data", {})
    if isinstance(job_data, dict) and job_data.get("name", "") in HEAVY_JOBS:
        return {"queue": "heavy"}
    return {"queue": "default"}


app.conf.task_routes = {"worker.execute_job": route_job}


_worker_db = None


@worker_process_init.connect
def init_worker_db(**kwargs) -> None:
    global _worker_db

    os.environ.setdefault("DATABASE_POOL_SIZE", "5")
    os.environ.setdefault("DATABASE_POOL_MAX_OVERFLOW", "5")

    if not os.getenv("DATABASE_URI", ""):
        _worker_db = None
        return

    from Database import Database  # type: ignore
    from logger import setup_logger  # type: ignore

    logger = setup_logger("WORKER")
    _worker_db = Database(logger)

    # Register plugin-shipped DB models so plugin jobs can query their own tables
    # (security-gated + checksum-verified for pro/external). Best-effort: a bad
    # plugin must never crash the worker child.
    try:
        from plugin_extensions import register_plugin_models  # type: ignore

        register_plugin_models(logger, db=_worker_db)
    except Exception as e:
        logger.error(f"Failed to register plugin DB models in worker: {e}")


@worker_process_shutdown.connect
def shutdown_worker_db(**kwargs) -> None:
    global _worker_db

    if _worker_db:
        _worker_db.close()
        _worker_db = None


def get_worker_db() -> Optional[Any]:
    return _worker_db
