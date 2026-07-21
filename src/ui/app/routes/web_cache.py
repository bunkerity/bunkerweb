from flask import Blueprint, Response, flash as flask_flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import API_CLIENT
from app.api_client import ApiClientError, ApiUnavailableError
from app.utils import flash

# Web cache = the NGINX proxy response cache (reverseproxy plugin), distinct from
# the "cache" blueprint which manages the job file cache.
web_cache = Blueprint("web_cache", __name__)

# Order mirrors CACHE_STATUS_VALUES in src/common/core/metrics/metrics.lua
CACHE_STATUSES = ("HIT", "MISS", "BYPASS", "EXPIRED", "STALE", "UPDATING", "REVALIDATED")


@web_cache.route("/web-cache", methods=["GET"])
@login_required
def web_cache_page():
    web_cache_status, web_cache_metrics = {}, {}
    try:
        web_cache_status = API_CLIENT.get_web_cache_status()
    except (ApiClientError, ApiUnavailableError) as e:
        flash(f"Error fetching web cache status: {e.message}", "error")
    try:
        web_cache_metrics = API_CLIENT.get_web_cache_metrics()
    except (ApiClientError, ApiUnavailableError) as e:
        flash(f"Error fetching web cache metrics: {e.message}", "error")

    try:
        instances = API_CLIENT.get_instances()
    except (ApiClientError, ApiUnavailableError):
        flash("Error fetching instances", "error")
        instances = []

    status_instances = web_cache_status.get("instances", web_cache_status)
    metrics_instances = web_cache_metrics.get("instances", web_cache_metrics)
    services_data = web_cache_status.get("services", [])

    # A hostname missing from web_cache_status/metrics means that one instance's
    # response was dropped by the API (see ApiCaller.send_to_apis) -- not that
    # caching is disabled there, so it's surfaced as "not reporting", not "disabled".
    instances_data = []
    for instance in instances:
        hostname = instance.get("hostname") if isinstance(instance, dict) else instance.hostname
        name = instance.get("name", hostname) if isinstance(instance, dict) else instance.name
        reachable = hostname in status_instances
        status_response = status_instances.get(hostname) or {}
        response_error = reachable and status_response.get("status") == "error"
        raw_status = status_response.get("data") or status_response.get("msg")
        status_data = raw_status if isinstance(raw_status, dict) else {}
        metrics_response = metrics_instances.get(hostname) or {}
        raw_metrics = metrics_response.get("data", metrics_response.get("msg"))
        metrics_data = raw_metrics if isinstance(raw_metrics, dict) else {}
        counters = {
            status: int(metrics_data[f"counter_cache_status_{status}"]) for status in CACHE_STATUSES if f"counter_cache_status_{status}" in metrics_data
        }
        instances_data.append(
            {
                "hostname": hostname,
                "name": name,
                "reachable": reachable,
                "response_error": response_error,
                "enabled": status_data.get("enabled"),
                "file_count": status_data.get("file_count"),
                "size_bytes": status_data.get("size_bytes"),
                "path": status_data.get("path"),
                "counters": counters,
                "total_requests": sum(counters.values()),
            }
        )

    total_requests = sum(i["total_requests"] for i in instances_data)
    status_totals = {status: sum(i["counters"].get(status, 0) for i in instances_data) for status in CACHE_STATUSES}

    summary = {
        "total_instances": len(instances_data),
        "reporting_count": sum(1 for i in instances_data if i["reachable"]),
        "total_services": len(services_data),
        "active_services": sum(1 for service in services_data if not service["is_draft"]),
        "enabled_services": sum(1 for service in services_data if service["enabled"] and not service["is_draft"]),
        "total_files": sum(i["file_count"] or 0 for i in instances_data),
        "total_size_bytes": sum(i["size_bytes"] or 0 for i in instances_data),
        "total_requests": total_requests,
        "hit_rate": round(status_totals["HIT"] / total_requests * 100, 1) if total_requests else None,
    }

    return render_template(
        "web_cache.html",
        instances_data=instances_data,
        cache_statuses=CACHE_STATUSES,
        status_totals=status_totals,
        summary=summary,
        services_data=services_data,
    )


@web_cache.route("/web-cache/purge", methods=["POST"])
@login_required
def web_cache_purge():
    if API_CLIENT.readonly:
        return Response("Database is in read-only mode", status=403)

    scope = request.form.get("scope", "all")
    urls = None
    if scope == "url":
        raw = (request.form.get("url") or "").strip()
        if not raw:
            flask_flash("A URL is required to purge by URL", "error")
            return redirect(url_for("web_cache.web_cache_page"))
        item = {"url": raw}
        key = (request.form.get("key") or "").strip()
        if key:
            item["key"] = key
        urls = [item]

    try:
        result = API_CLIENT.purge_web_cache(scope=scope, urls=urls)
        result_summary = result.get("summary", {})
        if result.get("status") == "partial":
            flask_flash(
                "Web cache purged on "
                f"{result_summary.get('succeeded', 0)} instance(s); "
                f"{result_summary.get('failed', 0)} failed and "
                f"{result_summary.get('skipped', 0)} unreachable instance(s) were skipped (nothing was queued).",
                "warning",
            )
        else:
            flask_flash("Web cache purged" + (f" for {urls[0]['url']}" if urls else " (all entries)"), "success")
    except (ApiClientError, ApiUnavailableError) as e:
        flask_flash(f"Error purging web cache: {e.message}", "error")

    return redirect(url_for("web_cache.web_cache_page"))
