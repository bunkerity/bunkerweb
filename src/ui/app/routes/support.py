from io import BytesIO
from json import dumps
from os import getenv, sep
from os.path import join
from pathlib import Path
from re import compile as re_compile, escape
from sys import path as sys_path
from zipfile import ZipFile

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for support module")

from flask import Blueprint, render_template, request, send_file
from flask_login import login_required

from app.dependencies import BW_CONFIG, DB

support = Blueprint("support", __name__)


# Display support page with service information and help resources.
# Renders the support template with available services for user reference
# and troubleshooting guidance.
@support.route("/support")
@login_required
def support_page():
    if DEBUG_MODE:
        logger.debug("support_page() called")
        services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" ")
        logger.debug(f"Retrieved {len(services)} services for support page: {services}")
    
    return render_template(
        "support.html",
        services=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" "),
    )


# Generate anonymized log files download as ZIP archive.
# Processes all log files in /var/log/bunkerweb, anonymizes sensitive data
# like domains and IP addresses, and creates downloadable ZIP file.
@support.route("/support/logs")
@login_required
def support_logs():
    if DEBUG_MODE:
        logger.debug("support_logs() called")
    
    logs_path = Path(sep, "var", "log", "bunkerweb")
    if DEBUG_MODE:
        logger.debug(f"Checking logs directory: {logs_path}")

    # If no files are in the directory, return an error message
    log_files = list(logs_path.glob("*.log"))
    if not log_files:
        if DEBUG_MODE:
            logger.debug("No log files found in directory")
        return "No log files found", 404

    if DEBUG_MODE:
        logger.debug(f"Found {len(log_files)} log files: {[f.name for f in log_files]}")

    # Get services once
    db_services = BW_CONFIG.get_config(methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))
    services = {domain for key, value in db_services.items() if key.endswith("_SERVER_NAME") for domain in value.split()}
    
    if DEBUG_MODE:
        logger.debug(f"Services to anonymize: {len(services)} domains")
        logger.debug(f"Service domains: {services}")

    # Compile regex patterns for IPv4, IPv6, and domain names
    ipv4_pattern = r"(?:\d{1,3}\.){3}\d{1,3}"
    ipv6_pattern = r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
    domains_pattern = "|".join(map(escape, services))

    if DEBUG_MODE:
        logger.debug(f"IPv4 pattern: {ipv4_pattern}")
        logger.debug(f"IPv6 pattern: {ipv6_pattern}")
        logger.debug(f"Domains pattern length: {len(domains_pattern)} characters")

    pattern = re_compile(rf"\b(?:(?P<domain>{domains_pattern})|(?P<ipv4>{ipv4_pattern})|(?P<ipv6>{ipv6_pattern}))\b")
    
    if DEBUG_MODE:
        logger.debug("Compiled anonymization regex patterns successfully")

    # Create zip buffer
    zip_buffer = BytesIO()
    total_lines_processed = 0
    
    with ZipFile(zip_buffer, "w") as zip_file:
        for file in log_files:
            if file.is_file():
                if DEBUG_MODE:
                    logger.debug(f"Processing log file: {file.name} (size: {file.stat().st_size} bytes)")
                
                # Process file line by line to reduce memory usage
                with file.open("rb") as f:
                    content = []
                    line_count = 0
                    anonymized_count = 0
                    
                    for line in f:
                        line_count += 1
                        line = line.decode("utf-8", errors="replace")
                        
                        # Count anonymizations
                        original_line = line
                        line = pattern.sub(
                            lambda m: "[ANONYMIZED_DOMAIN]" if m.group("domain") else ("[ANONYMIZED_IPv4]" if m.group("ipv4") else "[ANONYMIZED_IPv6]"),
                            line,
                        )
                        
                        if line != original_line:
                            anonymized_count += 1
                        
                        content.append(line)
                    
                    if DEBUG_MODE:
                        logger.debug(f"Processed {line_count} lines from {file.name}, anonymized {anonymized_count} lines")
                    
                    total_lines_processed += line_count
                    zip_file.writestr(file.name, "".join(content))

    if DEBUG_MODE:
        logger.debug(f"Total lines processed across all files: {total_lines_processed}")

    zip_buffer.seek(0)
    zip_size = len(zip_buffer.getvalue())
    
    if DEBUG_MODE:
        logger.debug(f"Created ZIP archive with {len(log_files)} files, total size: {zip_size} bytes")

    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name="logs.zip")


# Export service or global configuration as JSON download.
# Retrieves configuration data for specific service or all services
# and provides formatted JSON file for backup and analysis.
@support.route("/support/config")
@login_required
def support_config():
    if DEBUG_MODE:
        logger.debug("support_config() called")
    
    service = request.args.get("service")
    if DEBUG_MODE:
        logger.debug(f"Requested service config: {service}")

    if service:
        # Validate service exists
        if DEBUG_MODE:
            available_services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" ")
            logger.debug(f"Available services: {available_services}")
        
        if service not in BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" "):
            if DEBUG_MODE:
                logger.debug(f"Service '{service}' not found in available services")
            return "Service not found", 404

        if DEBUG_MODE:
            logger.debug(f"Retrieving configuration for service: {service}")

        service_config = DB.get_config(methods=True, with_drafts=True, service=service)
        
        if DEBUG_MODE:
            logger.debug(f"Service config retrieved with {len(service_config)} settings")
            logger.debug(f"Download filename: {service}_config.json")
        
        return send_file(
            BytesIO(dumps(service_config, indent=2).encode()), mimetype="application/json", as_attachment=True, download_name=f"{service}_config.json"
        )

    # Return global configuration
    if DEBUG_MODE:
        logger.debug("Retrieving global configuration (all services)")

    db_config = DB.get_config(methods=True, with_drafts=True)
    
    if DEBUG_MODE:
        logger.debug(f"Global config retrieved with {len(db_config)} settings")
        logger.debug("Download filename: bunkerweb_config.json")
    
    return send_file(BytesIO(dumps(db_config, indent=2).encode()), mimetype="application/json", as_attachment=True, download_name="bunkerweb_config.json")
