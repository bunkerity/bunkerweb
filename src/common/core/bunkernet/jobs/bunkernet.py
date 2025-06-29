#!/usr/bin/env python3

from logging import getLogger
from os import getenv, sep
from pathlib import Path
from traceback import format_exc
from requests import request as requests_request, ReadTimeout
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from common_utils import (  # type: ignore
    get_os_info, get_integration, get_version
)


def request(
    method: Literal["POST", "GET"], 
    url: str, 
    _id: Optional[str] = None, 
    *, 
    additional_data: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[int], Union[str, dict]]:
    # Send HTTP request to BunkerNet API with instance data.
    # Args: method (POST/GET), url (endpoint), _id (instance ID), 
    # additional_data (extra data)
    # Returns: Tuple of (success, status_code, response_data)
    logger = getLogger("BUNKERNET.request")
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"Making {method} request to {url}")
        logger.debug(f"Instance ID: {_id}")
        logger.debug(f"Additional data: {additional_data}")
    
    data = {
        "integration": get_integration(),
        "version": get_version(),
        "os": get_os_info(),
    }
    if _id:
        data["id"] = _id
    if additional_data:
        data.update(additional_data)

    try:
        bunkernet_server = getenv(
            'BUNKERNET_SERVER', 
            'https://api.bunkerweb.io'
        )
        full_url = f"{bunkernet_server}{url}"
        
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"Full URL: {full_url}")
            logger.debug(f"Request data: {data}")
        
        resp = requests_request(
            method,
            full_url,
            json=data,
            headers={"User-Agent": f"BunkerWeb/{data['version']}"},
            timeout=5,
        )
        status = resp.status_code
        
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"Response status: {status}")
        
        if status == 429:
            return True, 429, "rate limited"
        elif status == 403:
            return True, 403, "forbidden"

        raw_data: dict = resp.json()

        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"Response data: {raw_data}")

        assert "result" in raw_data
        assert "data" in raw_data
    except ReadTimeout:
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("Request timed out")
        return False, None, "request timed out"
    except Exception as e:
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(format_exc())
        return False, None, f"request failed: {e}"
    
    return True, status, raw_data


def register() -> Tuple[bool, Optional[int], Union[str, dict]]:
    # Register this BunkerWeb instance with the BunkerNet API.
    # Returns: Tuple of (success, status_code, response_data)
    logger = getLogger("BUNKERNET.register")
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("Registering instance with BunkerNet API")
    
    return request("POST", "/register")


def ping(_id: Optional[str] = None) -> Tuple[bool, Optional[int], Union[str, dict]]:
    # Send ping request to BunkerNet API to verify connectivity.
    # Args: _id (Instance ID, optional - will get from file if not provided)
    # Returns: Tuple of (success, status_code, response_data)
    logger = getLogger("BUNKERNET.ping")
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"Pinging BunkerNet API with ID: {_id}")
    
    return request("GET", "/ping", _id=_id or get_id())


def data() -> Tuple[bool, Optional[int], Union[str, dict]]:
    # Download threat intelligence data from BunkerNet API.
    # Returns: Tuple of (success, status_code, response_data)
    logger = getLogger("BUNKERNET.data")
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("Downloading threat data from BunkerNet API")
    
    return request("GET", "/db", _id=get_id())


def send_reports(
    reports: List[Dict[str, Any]]
) -> Tuple[bool, Optional[int], Union[str, dict]]:
    # Send threat reports to BunkerNet API for community sharing.
    # Args: reports (List of threat report dictionaries)
    # Returns: Tuple of (success, status_code, response_data)
    logger = getLogger("BUNKERNET.send_reports")
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"Sending {len(reports)} reports to BunkerNet API")
        for i, report in enumerate(reports):
            logger.debug(f"Report {i+1}: {report}")
    
    return request(
        "POST", 
        "/report", 
        _id=get_id(), 
        additional_data={"reports": reports}
    )


def get_id() -> str:
    # Get the BunkerNet instance ID from cache file.
    # Returns: Instance ID string
    logger = getLogger("BUNKERNET.get_id")
    id_path = Path(sep, "var", "cache", "bunkerweb", "bunkernet", "instance.id")
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"Reading instance ID from: {id_path}")
    
    instance_id = id_path.read_text(encoding="utf-8").strip()
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"Retrieved instance ID: {instance_id}")
    
    return instance_id