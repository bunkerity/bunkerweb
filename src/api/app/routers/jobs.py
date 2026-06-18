from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from ..celery_app import get_celery_app
from ..schemas import DispatchJobsRequest, RunJobsRequest

from ..auth.guard import guard
from ..utils import get_db

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", dependencies=[Depends(guard)])
def list_jobs() -> JSONResponse:
    """List all jobs with their history and cache metadata."""
    jobs = get_db().get_jobs()
    return JSONResponse(status_code=200, content={"status": "success", "jobs": jobs})


@router.post("/run", dependencies=[Depends(guard)])
def run_jobs(payload: RunJobsRequest) -> JSONResponse:
    """Trigger execution of specified jobs' plugins.

    Args:
        payload: Request containing list of jobs to run with plugin and name
    """
    plugins = [j.plugin for j in payload.jobs]

    ret = get_db().checked_changes(["config"], plugins_changes=plugins.copy(), value=True)
    if ret:
        # DB returns error string on failure
        return JSONResponse(status_code=500, content={"status": "error", "message": str(ret)})
    return JSONResponse(status_code=202, content={"status": "success", "message": "Jobs scheduled"})


@router.post("/dispatch", dependencies=[Depends(guard)])
def dispatch_jobs(payload: DispatchJobsRequest) -> JSONResponse:
    """Dispatch jobs to Celery workers for execution."""
    celery = get_celery_app()
    if celery is None:
        return JSONResponse(status_code=503, content={"status": "error", "message": "Celery broker not configured"})

    run_ids = []
    for job in payload.jobs:
        run_id = str(uuid4())
        job_payload = {
            "name": job.name,
            "plugin_id": job.plugin_id,
            "file": job.file,
            "path": job.path,
            "every": job.every,
            "reload": job.reload,
            "async": job.run_async,
            "run_id": run_id,
            "dispatch_time": datetime.now(timezone.utc).isoformat(),
        }
        # HEAVY_JOBS mirrors src/worker/app.py — keeps queue routing in sync
        # without importing worker package on the API side.
        HEAVY_JOBS = {
            "backup-data",
            "bunkernet-data",
            "bunkernet-register",
            "certbot-auth",
            "certbot-cleanup",
            "certbot-deploy",
            "certbot-new",
            "certbot-renew",
            "coreruleset-nightly",
            "download-crs-plugins",
            "download-plugins",
            "download-pro-plugins",
            "push-configs",
        }
        queue = "heavy" if job.name in HEAVY_JOBS else "default"
        try:
            celery.send_task("worker.execute_job", args=[job_payload], task_id=run_id, queue=queue)
        except Exception as exc:
            return JSONResponse(status_code=502, content={"status": "error", "message": f"Failed to dispatch jobs: {exc}"})
        run_ids.append({"name": job.name, "run_id": run_id})

    return JSONResponse(
        status_code=202,
        content={"status": "success", "message": "Jobs dispatched", "runs": run_ids},
    )


@router.get("/queue", dependencies=[Depends(guard)])
def get_jobs_queue() -> JSONResponse:
    """Get the current state of the Celery worker queues."""
    celery = get_celery_app()
    if celery is None:
        return JSONResponse(status_code=503, content={"status": "error", "message": "Celery broker not configured"})

    inspect = celery.control.inspect(timeout=2.0)
    try:
        active = inspect.active() or {}
        scheduled = inspect.scheduled() or {}
        reserved = inspect.reserved() or {}
        stats = inspect.stats() or {}
    except Exception:
        active, scheduled, reserved, stats = {}, {}, {}, {}

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "active": active,
            "scheduled": scheduled,
            "reserved": reserved,
            "stats": stats,
        },
    )
