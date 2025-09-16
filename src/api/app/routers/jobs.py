from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from ..schemas import RunJobsRequest

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
