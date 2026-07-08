from flask import Blueprint, Response, flash as flask_flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import API_CLIENT
from app.api_client import ApiClientError, ApiUnavailableError
from app.utils import flash

# Web cache = the NGINX proxy response cache (reverseproxy plugin), distinct from
# the "cache" blueprint which manages the job file cache. This page is plumbing +
# an unstyled stub; the visual design lands in a later Claude design pass.
web_cache = Blueprint("web_cache", __name__)


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

    return render_template("web_cache.html", web_cache_status=web_cache_status, web_cache_metrics=web_cache_metrics)


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
        urls = [{"url": raw}]

    try:
        API_CLIENT.purge_web_cache(scope=scope, urls=urls)
        flask_flash("Web cache purge requested" + (f" for {urls[0]['url']}" if urls else " (all entries)"), "success")
    except (ApiClientError, ApiUnavailableError) as e:
        flask_flash(f"Error purging web cache: {e.message}", "error")

    return redirect(url_for("web_cache.web_cache_page"))
