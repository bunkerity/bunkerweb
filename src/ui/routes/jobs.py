# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request

from utils import get_core_format_res
import json
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/jobs"

jobs = Blueprint('jobs', __name__)

@jobs.route(f"{PREFIX}", methods=['GET'])
def get_jobs():
    """ Get all jobs """
    return get_core_format_res(f"{CORE_API}/jobs", "GET", "", "Retrieve jobs")

@jobs.route(f"{PREFIX}/<str:job_name>/run", methods=['POST'])
def run_job(job_name):
    """ Send to scheduler task to run a job async """
    job_name = job_name
    # is_valid_model(job_name, Model) True | False
    args = request.args.to_dict() 
    method = args.get("method") or "ui"
    # is_valid_model(method, Model) True | False
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/run?method={method}", "POST", "", f"Run job {job_name}")

@jobs.route(f"{PREFIX}/<str:job_name>/cache/<str:file_name>", methods=['GET'])
def get_job_cache_file(job_name, file_name):
    """ Get a file from cache related to a job """
    job_name = job_name
    # is_valid_model(job_name, Model) True | False
    file_name = file_name
    # is_valid_model(file_name, Model) True | False
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{file_name}", "GET", "", f"Get file {file_name} from cache for job {job_name}")

@jobs.route(f"{PREFIX}/<str:job_name>/cache/<str:file_name>", methods=['DELETE'])
def delete_job_file_cache(job_name, file_name):
    """ Delete a file from cache related to a job """
    job_name = job_name
    # is_valid_model(job_name, Model) True | False
    file_name = file_name
    # is_valid_model(file_name, Model) True | False
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{file_name}", "DELETE", "", f"Delete file {file_name} from cache for job {job_name}")

@jobs.route(f"{PREFIX}/<str:job_name>/cache/<str:file_name>", methods=['PUT'])
def upload_job_file_cache(job_name, file_name):
    """ Upload a file to cache for a job """
    job_name = job_name
    # is_valid_model(job_name, Model) True | False
    file_name = file_name
    # is_valid_model(file_name, Model) True | False
    args = request.args.to_dict() 
    service_id = args.get("service_id") or None
    # is_valid_model(service_id, Model) True | False
    checksum = args.get("checksum") or None
    # is_valid_model(checksum, Model) True | False
    cache_file_bytes = request.get_data()
    # is_valid_model(cache_file_bytes, Model) True | False
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{file_name}?cache_file={cache_file}&service_id={service_id}&checksum={checksum}", "PUT", cache_file_bytes, f"Upload file {file_name} to cache {cache_file}")
