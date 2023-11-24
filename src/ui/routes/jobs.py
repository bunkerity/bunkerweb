# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from utils import get_core_format_res
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
def run_job():
    """Send to scheduler task to run a job async"""
    # is_valid_model(job_name, Model) True | False
    args = request.args.to_dict()
    method = args.get("method") or "ui"
    # is_valid_model(method, Model) True | False
    job_name = args.get("job_name") or ""
    # is_valid_model(job_name, Model) True | False
    return get_core_format_res(f"{CORE_API}/jobs/run?method={method}&job_name={job_name}", "POST", "", f"Run job {job_name}")


@jobs.route(f"{PREFIX}/<string:job_name>/cache/<string:file_name>", methods=["GET"])
@jwt_required()
def get_job_cache_file(job_name, file_name):
    """Get a file from cache related to a job"""
    args = request.args.to_dict()
    service_id = args.get("service_id") or ""
    # is_valid_model(service_id, Model) True | False
    # is_valid_model(job_name, Model) True | False
    # is_valid_model(file_name, Model) True | False
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{file_name}{f'?service_id={service_id}' if service_id else '' }", "GET", "", f"Get file {file_name} from cache for job {job_name}")


@jobs.route(f"{PREFIX}/<string:job_name>/cache/<string:file_name>", methods=["DELETE"])
@jwt_required()
def delete_job_file_cache(job_name, file_name):
    """Delete a file from cache related to a job"""
    # is_valid_model(job_name, Model) True | False
    # is_valid_model(file_name, Model) True | False
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{file_name}", "DELETE", "", f"Delete file {file_name} from cache for job {job_name}")


@jobs.route(f"{PREFIX}/<string:job_name>/cache/<string:file_name>", methods=["PUT"])
@jwt_required()
def upload_job_file_cache(job_name, file_name):
    """Upload a file to cache for a job"""
    # is_valid_model(job_name, Model) True | False
    # is_valid_model(file_name, Model) True | False
    args = request.args.to_dict()
    service_id = args.get("service_id") or None
    # is_valid_model(service_id, Model) True | False
    checksum = args.get("checksum") or None
    # is_valid_model(checksum, Model) True | False
    cache_file = args.get("cache_file") or None
    # is_valid_model(cache_file, Model) True | False
    cache_file_bytes = request.get_data()
    # is_valid_model(cache_file_bytes, Model) True | False
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{file_name}?cache_file={cache_file}&service_id={service_id}&checksum={checksum}", "PUT", cache_file_bytes, f"Upload file {file_name} to cache {cache_file}")
