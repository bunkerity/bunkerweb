import os
from typing import Any, Optional

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown
from kombu import Queue

from job_queues import HEAVY_JOBS, queue_for  # type: ignore # noqa: F401 (HEAVY_JOBS re-exported for callers importing it from here)

app = Celery("bunkerweb", include=["worker.tasks"])

app.conf.update(
    # 127.0.0.1 rather than localhost: on a dual-stack host localhost can resolve to ::1
    # first while Redis/Valkey binds v4 only, which fails the connection outright. The
    # Linux packaging (src/linux/scripts/bunkerweb-worker.sh) and the all-in-one entrypoint
    # already default to the literal address -- this keeps every default in step.
    broker_url=os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"),
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
    # At-least-once delivery. With acks_late=False the broker acked on RECEIPT, so a worker
    # killed mid-job lost that job silently -- no retry, no error, and the scheduler believed
    # it ran. A certbot renewal that never happened looks identical to one that did.
    #
    # These two settings cover different halves and both are needed:
    #   * acks_late alone covers the whole worker/container dying (nothing ever acks, the
    #     broker redelivers);
    #   * it does NOT cover a single prefork child killed by a signal -- Celery acknowledges
    #     those even under acks_late, deliberately, to stop a task that segfaults from looping
    #     forever (celery/worker/request.py::on_failure). reject_on_worker_lost overrides that,
    #     which is what catches the common case: the cgroup OOM-killing a heavy job.
    #
    # Removing Celery's loop protection means we owe our own bound: tasks.py counts deliveries
    # per task id and drops a job that keeps killing its worker. Do not enable one without the
    # other.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=1800,
    task_soft_time_limit=900,
    worker_max_tasks_per_child=1,
    worker_max_memory_per_child=300000,
    worker_prefetch_multiplier=1,
    worker_soft_shutdown_timeout=900.0,
    worker_hijack_root_logger=False,
    # Celery redirects sys.stdout/sys.stderr in every prefork child to a LoggingProxy, which
    # deliberately drops writes coming from a logging handler so a handler cannot recurse into
    # itself. `logger.py` binds its StreamHandler to sys.stderr, so that dropped EVERY line a job
    # or tasks.py logged inside the child: `docker logs bw-worker` showed Celery's own
    # "task received/succeeded" lines and nothing else, while output from a subprocess a job
    # spawns (the generator) came through because it writes to the fd directly. Every job failure
    # was therefore invisible from outside and had to be reconstructed from bw_jobs_runs.
    worker_redirect_stdouts=False,
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


def route_job(name: str, args: tuple[Any, ...], kwargs: dict[str, Any], options: dict[str, Any], task=None, **kw) -> dict[str, str]:
    job_data = args[0] if args else kwargs.get("job_data", {})
    if not isinstance(job_data, dict):
        return {"queue": "default"}
    return {"queue": queue_for(job_data.get("name", ""))}


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
