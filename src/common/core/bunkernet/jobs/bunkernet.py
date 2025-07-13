#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from requests import request as requests_request, ReadTimeout
from sys import path as sys_path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="bunkernet",
    log_file_path="/var/log/bunkerweb/bunkernet.log"
)

logger.debug("Debug mode enabled for bunkernet")

from common_utils import get_os_info, get_integration, get_version  # type: ignore


# Send HTTP request to bunkernet API with system information and authentication.
def request(
    method: Literal["POST", "GET"], url: str, _id: Optional[str] = None, *, additional_data: Dict[str, Any] = None
) -> Tuple[bool, Optional[int], Union[str, dict]]:
    logger.debug(f"request() called: method={method}, url={url}, id={_id}")
    
    data = {
        "integration": get_integration(),
        "version": get_version(),
        "os": get_os_info(),
    }
    if _id:
        data["id"] = _id
    if additional_data:
        data.update(additional_data)
        logger.debug(f"Added additional data: {list(additional_data.keys())}")

    logger.debug(f"Request data prepared: {list(data.keys())}")
    
    try:
        server_url = getenv('BUNKERNET_SERVER', 'https://api.bunkerweb.io')
        full_url = f"{server_url}{url}"
        logger.debug(f"Making {method} request to: {full_url}")
        
        resp = requests_request(
            method,
            full_url,
            json=data,
            headers={"User-Agent": f"BunkerWeb/{data['version']}"},
            timeout=5,
        )
        status = resp.status_code
        logger.debug(f"Response status code: {status}")
        
        if status == 429:
            logger.warning("Rate limited by bunkernet API")
            return True, 429, "rate limited"
        elif status == 403:
            logger.warning("Forbidden by bunkernet API")
            return True, 403, "forbidden"

        raw_data: dict = resp.json()
        logger.debug(f"Response data keys: {list(raw_data.keys()) if isinstance(raw_data, dict) else 'not dict'}")

        assert "result" in raw_data
        assert "data" in raw_data
        logger.debug("Response validation successful")
        
    except ReadTimeout:
        logger.warning("Request to bunkernet API timed out")
        return False, None, "request timed out"
    except Exception as e:
        logger.exception("Exception during bunkernet API request")
        return False, None, f"request failed: {e}"
        
    logger.debug("Request completed successfully")
    return True, status, raw_data


# Register this instance with the bunkernet service.
def register() -> Tuple[bool, Optional[int], Union[str, dict]]:
    logger.debug("register() called")
    return request("POST", "/register")


# Send ping to bunkernet service to check connectivity and status.
def ping(_id: Optional[str] = None) -> Tuple[bool, Optional[int], Union[str, dict]]:
    logger.debug(f"ping() called with id: {_id}")
    return request("GET", "/ping", _id=_id or get_id())


# Retrieve threat intelligence data from bunkernet service.
def data() -> Tuple[bool, Optional[int], Union[str, dict]]:
    logger.debug("data() called")
    return request("GET", "/db", _id=get_id())


# Send security reports to bunkernet for threat intelligence sharing.
def send_reports(reports: List[Dict[str, Any]]) -> Tuple[bool, Optional[int], Union[str, dict]]:
    logger.debug(f"send_reports() called with {len(reports)} reports")
    return request("POST", "/report", _id=get_id(), additional_data={"reports": reports})


# Get the instance ID from the local cache file.
def get_id() -> str:
    logger.debug("get_id() called")
    id_file = Path(sep, "var", "cache", "bunkerweb", "bunkernet", "instance.id")
    logger.debug(f"Reading instance ID from: {id_file}")
    try:
        instance_id = id_file.read_text(encoding="utf-8").strip()
        logger.debug(f"Retrieved instance ID: {instance_id}")
        return instance_id
    except Exception as e:
        logger.exception("Exception while reading instance ID")
        raise
