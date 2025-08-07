#!/usr/bin/env python3

from Database import Database
from jobs import Job
from logger import setup_logger
from datetime import datetime, timedelta
from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
import subprocess
import json
import requests

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)


# LOGGER = setup_logger("ADIDOS.monitor", getenv("LOG_LEVEL", "info"))
LOG_LEVEL = "info" if getenv("ADIDOS_LOG") == "yes" else getenv("LOG_LEVEL", "error")

LOGGER = setup_logger("ADIDOS.monitor", LOG_LEVEL)

exit_status = 0

def send_webhook(message):
    """Send webhook notification"""
    webhook_url = getenv("ADIDOS_WEB_HOOK_URL")
    webhook_body = getenv("ADIDOS_WEB_HOOK_BODY")
    
    if not webhook_url or not webhook_body:
        LOGGER.debug("Webhook URL or body not configured, skipping webhook")
        return
    
    try:
        # Replace placeholder with actual message
        body = webhook_body.replace("{{MESSAGE}}", message)
        
        # Try to parse as JSON, if fails send as plain text
        try:
            json_body = json.loads(body)
            headers = {'Content-Type': 'application/json'}
            response = requests.post(webhook_url, json=json_body, headers=headers, timeout=10)
        except json.JSONDecodeError:
            headers = {'Content-Type': 'text/plain'}
            response = requests.post(webhook_url, data=body, headers=headers, timeout=10)
        
        if response.status_code == 200:
            LOGGER.info(f"Webhook sent successfully: {message}")
        else:
            LOGGER.error(f"Webhook failed with status {response.status_code}: {response.text}")
            
    except Exception as e:
        LOGGER.error(f"Failed to send webhook: {e}")

try:
    LOGGER.info("ADIDOS monitoring is started")
    # Check if ADIDOS monitoring is enabled
    if getenv("USE_ADIDOS", "no") != "yes":
        LOGGER.info("ADIDOS monitoring is disabled")
        sys_exit(0)
    LOGGER.info("ADIDOS monitoring is enabled")

    # Configuration
    monitor_host = getenv("ADIDOS_HOST", "85.198.111.8")
    ssh_key_path = getenv(
        "ADIDOS_SSH_KEY", "/usr/share/bunkerweb/scheduler/.ssh/id_rsa")
    high_threshold = float(getenv("ADIDOS_THRESHOLD_HIGH", "80"))
    low_threshold = float(getenv("ADIDOS_THRESHOLD_LOW", "50"))
    cooldown_minutes = int(getenv("ADIDOS_COOLDOWN_MINUTES", "5"))

    if not monitor_host:
        LOGGER.error("ADIDOS_HOST not configured")
        sys_exit(1)

    # Initialize job and database
    JOB = Job(LOGGER, __file__)
    DB = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI", None))

    # Get current load via SSH
    ssh_cmd = [
        "ssh",
        "-i", ssh_key_path,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        monitor_host,
        "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
    ]

    try:
        result = subprocess.run(
            ssh_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            LOGGER.error(f"SSH command failed: {result.stderr}")
            sys_exit(1)

        current_load = float(result.stdout.strip())
        LOGGER.info(f"Current load: {current_load}%")
    except Exception as e:
        LOGGER.error(f"Failed to get load: {e}")
        sys_exit(1)

    # Get cached state
    cached_state = JOB.get_cache("antibot_state")
    if cached_state:
        try:
            # Parse cached state
            if isinstance(cached_state, str):
                cached_data = cached_state.split(",")
            elif isinstance(cached_state, bytes):
                cached_data = cached_state.decode().split(",")
            elif isinstance(cached_state, dict) and 'data' in cached_state:
                # Handle dict format
                if isinstance(cached_state['data'], bytes):
                    cached_data = cached_state['data'].decode().split(",")
                else:
                    cached_data = str(cached_state['data']).split(",")
            else:
                raise ValueError(
                    f"Unexpected cached_state type: {type(cached_state)}")

            if len(cached_data) >= 2:
                cached_antibot, last_activation_str = cached_data[0], cached_data[1]
                last_activation = datetime.fromisoformat(last_activation_str)
            else:
                cached_antibot = "no"
                last_activation = datetime.now()
        except Exception as e:
            LOGGER.warning(f"Failed to parse cached state: {e}")
            cached_antibot = "no"
            last_activation = datetime.now()
    else:
        cached_antibot = "yes"
        last_activation = datetime.now()
        cache_data = f"{cached_antibot},{datetime.now().isoformat()}"
        JOB.cache_file("antibot_state", cache_data.encode())

    # Decision logic
    should_enable = False
    should_disable = False
    new_antibot_state = current_antibot = cached_antibot

    if current_load >= high_threshold and current_antibot == "no":
        should_enable = True
        new_antibot_state = "yes"
        LOGGER.info(
            f"Load {current_load}% >= {high_threshold}%, should enable antibot")
    elif current_load <= low_threshold and current_antibot == "yes":
        # Check cooldown period
        time_since_activation = datetime.now() - last_activation
        if time_since_activation >= timedelta(minutes=cooldown_minutes):
            should_disable = True
            new_antibot_state = "no"
            LOGGER.info(
                f"Load {current_load}% <= {low_threshold}% and cooldown passed, should disable antibot")
        else:
            LOGGER.info(
                f"Load low but cooldown period not passed ({time_since_activation} < {cooldown_minutes}min)")

    # Apply changes
    if should_enable:
        LOGGER.info("Decision: Enable antibot (captcha mode)")
        # Update cache with new activation time
        cache_data = f"yes,{datetime.now().isoformat()}"
        JOB.cache_file("antibot_state", cache_data.encode())
        config = DB.get_config(with_drafts=True)
        services = getenv("ADIDOS_SERVICES", "").split(" ")
        config_update = config

        # Save to database
        try:
            captcha_type = getenv("ADIDOS_CAPTCHA_TYPE", "captcha")
            for service in services:
                config_update[f"{service}_USE_ANTIBOT"] = captcha_type
            result = DB.save_config(
                config_update, method="scheduler", changed=True)
            if isinstance(result, str):
                LOGGER.warning(
                    f"Failed to save antibot state to database: {result}")
            else:
                LOGGER.info("Antibot state successfully saved to database")
                # Send webhook notification
                send_webhook(f"ADIDOS: antibot enabled, current load {current_load}%")
        except Exception as e:
            LOGGER.error(f"Exception while saving to database: {e}")

    elif should_disable:
        LOGGER.info("Decision: Disable antibot")
        # Clear activation time from cache
        cache_data = f"no,{datetime.now().isoformat()}"
        JOB.cache_file("antibot_state", cache_data.encode())
        
        # Get config and services for disabling
        config = DB.get_config(with_drafts=True)
        services = getenv("ADIDOS_SERVICES", "").split(" ")
        config_update = config

        # Save to database
        try:
            for service in services:
                config_update[f"{service}_USE_ANTIBOT"] = "no"
            result = DB.save_config(
                config_update, method="scheduler", changed=True)
            if isinstance(result, str):
                LOGGER.warning(
                    f"Failed to save antibot state to database: {result}")
            else:
                LOGGER.info("Antibot state successfully saved to database")
                # Send webhook notification
                time_since_activation = datetime.now() - last_activation
                hours = int(time_since_activation.total_seconds() // 3600)
                minutes = int((time_since_activation.total_seconds() % 3600) // 60)
                time_format = f"{hours:02d}h {minutes:02d}m" if hours > 0 else f"{minutes} minutes"
                send_webhook(f"ADIDOS: antibot disabled after {time_format} activity, current load {current_load}%")
        except Exception as e:
            LOGGER.error(f"Exception while saving to database: {e}")
    else:
        LOGGER.info(
            f"Decision: No change needed (current: {current_antibot}, load: {current_load}%)")

except SystemExit as e:
    LOGGER.info(f"Nothing to do, exit status: {e.code}")

    exit_status = e.code
except BaseException as e:
    exit_status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running adidos-monitor.py: {e}")

sys_exit(exit_status)
