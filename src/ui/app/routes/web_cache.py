from flask import Blueprint, Response, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import API_CLIENT
from app.i18n import translated
from app.api_client import ApiClientError, ApiUnavailableError
from app.utils import flash, is_readonly_request

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
        flash(translated("web_cache.flash.error_fetching_web_cache_status", message=e.message) or f"Error fetching web cache status: {e.message}", "error")
    try:
        web_cache_metrics = API_CLIENT.get_web_cache_metrics()
    except (ApiClientError, ApiUnavailableError) as e:
        flash(translated("web_cache.flash.error_fetching_web_cache_metrics", message=e.message) or f"Error fetching web cache metrics: {e.message}", "error")

    try:
        instances = API_CLIENT.get_instances()
    except (ApiClientError, ApiUnavailableError):
        flash(translated("flash.error_fetching_instances") or "Error fetching instances", "error")
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
        return Response(translated("flash.database_read_only_mode") or "Database is in read-only mode", status=403)
    if is_readonly_request(API_CLIENT.readonly):
        return Response(translated("flash.do_not_have_write_permission") or "You do not have the write permission", status=403)

    scope = request.form.get("scope", "all")
    urls = None
    if scope == "url":
        raw = (request.form.get("url") or "").strip()
        if not raw:
            flash(translated("web_cache.flash.url_required_purge_by_url") or "A URL is required to purge by URL", "error", save=False)
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
            flash(
                translated(
                    "web_cache.flash.web_cache_purged_instance_failed_unreachable",
                    value=result_summary.get("succeeded", 0),
                    value2=result_summary.get("failed", 0),
                    value3=result_summary.get("skipped", 0),
                )
                or "Web cache purged. "
                f"Instances purged: {result_summary.get('succeeded', 0)}, "
                f"failed: {result_summary.get('failed', 0)}, "
                f"unreachable and skipped: {result_summary.get('skipped', 0)} (nothing was queued).",
                "warning",
                save=False,
            )
        else:
            # `flash()`, not `flask_flash(..., "success")`: the wrapper omits the category for
            # "success" so Flask defaults it to "message" -- `flash.html` looks up `flash.<category>`,
            # and there is no `flash.success` key (M24). Passing "success" straight through echoed
            # the raw key as the toast header.
            if urls:
                flash(translated("web_cache.flash.purged_for_url", url=urls[0]["url"]) or f"Web cache purged for {urls[0]['url']}")
            else:
                flash(translated("web_cache.flash.purged_all_entries") or "Web cache purged (all entries)")
    except (ApiClientError, ApiUnavailableError) as e:
        flash(translated("web_cache.flash.error_purging_web_cache", message=e.message) or f"Error purging web cache: {e.message}", "error", save=False)

    return redirect(url_for("web_cache.web_cache_page"))
