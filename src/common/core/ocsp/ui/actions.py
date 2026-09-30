"""
OCSP Plugin UI Actions - Status Card Display

This module provides the pre_render function that generates status cards
displayed on the OCSP plugin page (/plugins/ocsp). It shows:

- OCSP async validation job status (ping)
- Count of cached OCSP responses
- Count of pending certificate validations
- Link to configuration settings page
- Link to status overview page

The pre_render function is automatically called by the plugin page renderer
to populate status information from metrics and job status.
"""

from logging import getLogger
from traceback import format_exc

from flask import url_for


def pre_render(**kwargs):
    """
    Generate status card data for OCSP plugin page display.

    Retrieves real-time metrics from BunkerWeb instances to populate
    status cards showing OCSP job health and statistics.

    Args:
        **kwargs: Framework-provided dependencies:
            - bw_instances_utils: Access to instance metrics and ping data

    Returns:
        dict: Status card data with keys for each card type:

            ping_status: OCSP async validation job status
                - value: "unknown" | "yes" | "no"
                - action_url: Link to status overview page
                - action_label: "View Status Overview"

            counter_ocsp_cache_entries: Number of cached OCSP responses
                - value: int (count of cached responses)

            counter_ocsp_pending: Pending certificate validations
                - value: int (count of pending validations)

            info_configuration: Configuration link card
                - action_url: Link to settings page
                - action_label: "Open Settings"
    """
    logger = getLogger("UI")
    try:
        overview_url = url_for("ocsp.ocsp_overview")
        settings_url = url_for("ocsp.ocsp_settings")
    except Exception:
        overview_url = "/ocsp"
        settings_url = "/ocsp/settings"

    ret = {
        "ping_status": {
            "title": "OCSP JOB STATUS",
            "value": "unknown",
            "col-size": "col-12 col-md-4",
            "card-classes": "h-100",
            "subtitle": "Async validation job",
            "action_url": overview_url,
            "action_label": "View Status Overview",
            "action_i18n": "ocsp.overview",
        },
        "counter_ocsp_cache_entries": {
            "value": 0,
            "title": "CACHED RESPONSES",
            "subtitle": "OCSP responses in cache",
            "subtitle_color": "success",
            "svg_color": "success",
            "col-size": "col-12 col-md-4",
            "card-classes": "h-100",
        },
        "counter_ocsp_pending": {
            "value": 0,
            "title": "PENDING VALIDATIONS",
            "subtitle": "Certificates awaiting validation",
            "subtitle_color": "warning",
            "svg_color": "warning",
            "col-size": "col-12 col-md-4",
            "card-classes": "h-100",
        },
        "info_configuration": {
            "title": "CONFIGURATION",
            "value": "Configure OCSP stapling globally and per-service",
            "col-size": "col-12 col-md-12",
            "card-classes": "h-100",
            "action_url": settings_url,
            "action_label": "Open Settings",
        },
    }
    try:
        # Try to get ping status for OCSP job
        ping_data = kwargs["bw_instances_utils"].get_ping("ocsp")
        if ping_data and isinstance(ping_data, dict):
            ret["ping_status"]["value"] = ping_data.get("status", "unknown")
    except BaseException as e:
        logger.debug(format_exc())
        logger.warning(f"Failed to get OCSP ping status: {e}")

    try:
        # Try to get metrics from instances
        metrics = kwargs["bw_instances_utils"].get_metrics("ocsp")
        if isinstance(metrics, dict):
            # Update cache entries count
            cache_entries = metrics.get("ocsp_cache_entries", 0)
            if isinstance(cache_entries, (int, float)):
                ret["counter_ocsp_cache_entries"]["value"] = int(cache_entries)

            # Update pending validations count
            pending = metrics.get("ocsp_pending_validations", 0)
            if isinstance(pending, (int, float)):
                ret["counter_ocsp_pending"]["value"] = int(pending)
    except BaseException as e:
        logger.debug(format_exc())
        logger.warning(f"Failed to get OCSP metrics: {e}")

    return ret


def ocsp(**kwargs):
    pass
