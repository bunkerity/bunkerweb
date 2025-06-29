from logging import getLogger
from os import getenv
from traceback import format_exc


def pre_render(**kwargs):
    # Prepare BunkerNet data for UI rendering.
    # Args: **kwargs containing bw_instances_utils and db
    # Returns: dict with UI data for BunkerNet dashboard
    logger = getLogger("UI")
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("Starting BunkerNet pre_render")
    
    # Initialize return structure with default values
    ret = {
        "ping_status": {
            "title": "BUNKERNET STATUS",
            "value": "error",
            "col-size": "col-12 col-md-4",
            "card-classes": "h-100",
        },
        "info_instance_id": {
            "value": "Unknown",
            "title": "Instance ID",
            "subtitle_color": "primary",
            "svg_color": "primary",
            "col-size": "col-12 col-md-8",
            "card-classes": "h-100",
        },
        "list_bunkernet_ips": {
            "data": {},
            "types": {0: "ip-address"},
            "svg_color": "primary",
            "col-size": "col-12",
        },
    }
    
    try:
        # Get ping status from BunkerWeb instances
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("Getting BunkerNet ping status")
        
        ping_data = kwargs["bw_instances_utils"].get_ping("bunkernet")
        ret["ping_status"]["value"] = ping_data["status"]
        
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"Ping status: {ping_data['status']}")

        # Get instance ID from cache
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("Getting instance ID from cache")
        
        instance_id = kwargs["db"].get_job_cache_file(
            "bunkernet-register", 
            "instance.id"
        )
        
        if instance_id:
            instance_id_str = instance_id.decode("utf-8")
            ret["info_instance_id"]["value"] = instance_id_str
            
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"Instance ID: {instance_id_str}")

            # Get IP list from cache
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("Getting IP list from cache")
            
            ips_file = kwargs["db"].get_job_cache_file(
                "bunkernet-data", 
                "ip.list"
            )
            
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"IPs file: {ips_file is not None}")
            
            if ips_file:
                ips_file_content = ips_file.decode("utf-8")
                ip_list = _parse_ip_list(ips_file_content, logger)
                
                if ip_list:
                    ret["list_bunkernet_ips"]["data"]["ip"] = ip_list
                    
                    if getenv("LOG_LEVEL") == "debug":
                        logger.debug(f"Loaded {len(ip_list)} IPs")
        else:
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("No instance ID found in cache")
                
    except BaseException as e:
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(format_exc())
        logger.error(f"Failed to get bunkernet metrics: {e}")
        ret["error"] = str(e)

    if getenv("LOG_LEVEL") == "debug":
        logger.debug("BunkerNet pre_render completed")
    
    return ret


def _parse_ip_list(ips_file_content, logger):
    # Parse IP list content into a list of IP addresses.
    # Args: ips_file_content (string content of IP list file), 
    # logger (Logger instance for debugging)
    # Returns: list of IP addresses
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("Parsing IP list content")
    
    ip_list = []
    
    for ip in ips_file_content.split("\n"):
        ip = ip.strip()
        if ip:  # Skip empty lines
            ip_list.append(ip)
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"Parsed {len(ip_list)} IP addresses")
    
    return ip_list


def bunkernet(**kwargs):
    # Handle BunkerNet specific actions (currently placeholder).
    # Args: **kwargs for action handling
    logger = getLogger("UI")
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("BunkerNet action called")
    
    # Placeholder for future BunkerNet-specific actions
    pass