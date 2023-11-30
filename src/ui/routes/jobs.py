# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from middleware.validator import model_validator

from utils import get_core_format_res, get_req_data
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/jobs"

jobs = Blueprint("jobs", __name__)


@jobs.route(f"{PREFIX}", methods=["GET"])
@jwt_required()
def get_jobs():
    """Get all jobs"""
    return get_core_format_res(f"{CORE_API}/jobs", "GET", "", "Retrieve jobs")


@jobs.route(f"{PREFIX}/run", methods=["POST"])
@jwt_required()
@model_validator(queries={"method": "Method", "job_name": "JobName"})
def run_job():
    """Send to scheduler task to run a job async"""
    args, data, method, job_name = [get_req_data(request, ["method", "reload", "job_name"])[k] for k in ("args", "data", "method", "job_name")]
    return get_core_format_res(f"{CORE_API}/jobs/run?method={method if method else 'ui'}&job_name={job_name if job_name else ''}", "POST", "", f"Run job {job_name}")


@jobs.route(f"{PREFIX}/<string:job_name>/cache/<string:cache_name>", methods=["GET"])
@jwt_required()
@model_validator(queries={"service_id": "ServiceId"}, params={"job_name": "JobName", "cache_name": "CacheFileName"})
def get_job_cache_file(job_name, cache_name):
    """Get a file from cache related to a job"""
    args, data, service_id = [get_req_data(request, ["method", "reload", "service_id"])[k] for k in ("args", "data", "service_id")]
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{cache_name}{f'?service_id={service_id}' if service_id else '' }", "GET", "", f"Get file {cache_name} from cache for job {job_name}")


@jobs.route(f"{PREFIX}/<string:job_name>/cache/<string:cache_name>", methods=["DELETE"])
@jwt_required()
@model_validator(params={"job_name": "JobName", "cache_name": "CacheFileName"})
def delete_job_file_cache(job_name, cache_name):
    """Delete a file from cache related to a job"""
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{cache_name}", "DELETE", "", f"Delete file {cache_name} from cache for job {job_name}")


@jobs.route(f"{PREFIX}/<string:job_name>/cache/<string:cache_name>", methods=["PUT"])
@jwt_required()
@model_validator(is_body_json=False, queries={"service_id": "ServiceId", "checksum": "Checksum", "cache_file": "CacheFileName"}, params={"job_name": "JobName", "cache_name": "CacheFileName"})
def upload_job_file_cache(job_name, cache_name):
    """Upload a file to cache for a job"""
    args, data, service_id, checksum, cache_file = [get_req_data(request, ["method", "reload", "service_id", "checksum", "cache_file"])[k] for k in ("args", "data", "service_id", "checksum", "cache_file")]
    cache_file_bytes = request.get_data()
    return get_core_format_res(
        f"{CORE_API}/jobs/{job_name}/cache/{cache_name}?cache_file={cache_file if cache_file else ''}&service_id={service_id if service_id else ''}&checksum={checksum if checksum else ''}",
        "PUT",
        cache_file_bytes,
        f"Upload file {cache_name} to cache {cache_file}",
    )
