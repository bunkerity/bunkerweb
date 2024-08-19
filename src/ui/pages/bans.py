from base64 import b64encode
from datetime import datetime, timezone
from json import dumps, loads as json_loads
from math import floor
from time import time

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required
from redis import Redis, Sentinel

from builder.bans import bans_builder  # type: ignore

from pages.utils import get_remain, handle_error, verify_data_in_form

bans = Blueprint("bans", __name__)


@bans.route("/bans", methods=["GET", "POST"])
@login_required
def bans_page():
    if request.method == "POST":

        if current_app.db.readonly:
            return handle_error("Database is in read-only mode", "bans")

        # Check variables
        verify_data_in_form(data={"operation": ("ban", "unban")}, err_message="Invalid operation parameter on /bans.", redirect_url="bans")
        verify_data_in_form(data={"data": None}, err_message="Missing data parameter on /bans.", redirect_url="bans")

    redis_client = None
    db_config = current_app.bw_config.get_config(
        global_only=True,
        methods=False,
        filtered_settings=(
            "USE_REDIS",
            "REDIS_HOST",
            "REDIS_PORT",
            "REDIS_DB",
            "REDIS_TIMEOUT",
            "REDIS_KEEPALIVE_POOL",
            "REDIS_SSL",
            "REDIS_USERNAME",
            "REDIS_PASSWORD",
            "REDIS_SENTINEL_HOSTS",
            "REDIS_SENTINEL_USERNAME",
            "REDIS_SENTINEL_PASSWORD",
            "REDIS_SENTINEL_MASTER",
        ),
    )
    use_redis = db_config.get("USE_REDIS", "no") == "yes"
    redis_host = db_config.get("REDIS_HOST")
    if use_redis and redis_host:
        redis_port = db_config.get("REDIS_PORT", "6379")
        if not redis_port.isdigit():
            redis_port = "6379"
        redis_port = int(redis_port)

        redis_db = db_config.get("REDIS_DB", "0")
        if not redis_db.isdigit():
            redis_db = "0"
        redis_db = int(redis_db)

        redis_timeout = db_config.get("REDIS_TIMEOUT", "1000.0")
        try:
            redis_timeout = float(redis_timeout)
        except ValueError:
            redis_timeout = 1000.0

        redis_keepalive_pool = db_config.get("REDIS_KEEPALIVE_POOL", "10")
        if not redis_keepalive_pool.isdigit():
            redis_keepalive_pool = "10"
        redis_keepalive_pool = int(redis_keepalive_pool)

        redis_ssl = db_config.get("REDIS_SSL", "no") == "yes"
        username = db_config.get("REDIS_USERNAME", None) or None
        password = db_config.get("REDIS_PASSWORD", None) or None
        sentinel_hosts = db_config.get("REDIS_SENTINEL_HOSTS", [])

        if isinstance(sentinel_hosts, str):
            sentinel_hosts = [host.split(":") if ":" in host else (host, "26379") for host in sentinel_hosts.split(" ") if host]

        if sentinel_hosts:
            sentinel_username = db_config.get("REDIS_SENTINEL_USERNAME", None) or None
            sentinel_password = db_config.get("REDIS_SENTINEL_PASSWORD", None) or None
            sentinel_master = db_config.get("REDIS_SENTINEL_MASTER", "")

            sentinel = Sentinel(
                sentinel_hosts,
                username=sentinel_username,
                password=sentinel_password,
                ssl=redis_ssl,
                socket_timeout=redis_timeout,
                socket_connect_timeout=redis_timeout,
                socket_keepalive=True,
                max_connections=redis_keepalive_pool,
            )
            redis_client = sentinel.slave_for(sentinel_master, db=redis_db, username=username, password=password)
        else:
            redis_client = Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                username=username,
                password=password,
                socket_timeout=redis_timeout,
                socket_connect_timeout=redis_timeout,
                socket_keepalive=True,
                max_connections=redis_keepalive_pool,
                ssl=redis_ssl,
            )

        try:
            redis_client.ping()
        except BaseException:
            redis_client = None
            flash("Couldn't connect to redis, ban list might be incomplete", "error")

    def get_load_data():
        try:
            data = json_loads(request.form["data"])
            assert isinstance(data, list)
            return data
        except BaseException:
            return handle_error("Data must be a list of dict", "bans", False, "exception")

    if request.method == "POST" and request.form["operation"] == "unban":
        data = get_load_data()

        for unban in data:
            try:
                unban = json_loads(unban.replace('"', '"').replace("'", '"'))
            except BaseException:
                flash(f"Invalid unban: {unban}, skipping it ...", "error")
                current_app.logger.exception(f"Couldn't unban {unban['ip']}")
                continue

            if "ip" not in unban:
                flash(f"Invalid unban: {unban}, skipping it ...", "error")
                continue

            if redis_client:
                if not redis_client.delete(f"bans_ip_{unban['ip']}"):
                    flash(f"Couldn't unban {unban['ip']} on redis", "error")

            resp = current_app.bw_instances_utils.unban(unban["ip"])
            if resp:
                flash(f"Couldn't unban {unban['ip']} on the following instances: {', '.join(resp)}", "error")
            else:
                flash(f"Successfully unbanned {unban['ip']}")

        return redirect(url_for("loading", next=url_for("bans.bans_page"), message="Update bans"))

    if request.method == "POST" and request.form["operation"] == "ban":
        data = get_load_data()

        for ban in data:
            if not isinstance(ban, dict) or "ip" not in ban:
                flash(f"Invalid ban: {ban}, skipping it ...", "error")
                continue

            reason = ban.get("reason", "ui")
            ban_end = 86400.0
            if "ban_end" in ban:
                try:
                    ban_end = float(ban["ban_end"])
                except ValueError:
                    continue
                ban_end = (datetime.fromtimestamp(ban_end) - datetime.now(timezone.utc)).total_seconds()

            if redis_client:
                ok = redis_client.set(f"bans_ip_{ban['ip']}", dumps({"reason": reason, "date": time()}))
                if not ok:
                    flash(f"Couldn't ban {ban['ip']} on redis", "error")
                redis_client.expire(f"bans_ip_{ban['ip']}", int(ban_end))

            resp = current_app.bw_instances_utils.ban(ban["ip"], ban_end, reason)
            if resp:
                flash(f"Couldn't ban {ban['ip']} on the following instances: {', '.join(resp)}", "error")
            else:
                flash(f"Successfully banned {ban['ip']}")

        return redirect(url_for("loading", next=url_for("bans.bans_page"), message="Update bans"))

    bans = []
    if redis_client:
        for key in redis_client.scan_iter("bans_ip_*"):
            ip = key.decode("utf-8").replace("bans_ip_", "")
            data = redis_client.get(key)
            if not data:
                continue
            exp = redis_client.ttl(key)
            bans.append({"ip": ip, "exp": exp} | json_loads(data))  # type: ignore
    instance_bans = current_app.bw_instances_utils.get_bans()

    # Prepare data
    timestamp_now = time()

    for ban in instance_bans:
        if not any(b["ip"] == ban["ip"] for b in bans):
            bans.append(ban)

    # Get the last 100 bans
    bans = bans[:100]
    reasons = set()
    remains = set()

    for ban in bans:
        exp = ban.pop("exp", 0)
        # Add remain
        remain = ("unknown", "unknown") if exp <= 0 else get_remain(exp)
        ban["remain"] = remain[0]
        remains.add(remain[1])
        # Convert stamp to date
        ban["ban_start_date"] = datetime.fromtimestamp(floor(ban["date"])).strftime("%Y/%m/%d at %H:%M:%S %Z")
        ban["ban_end_date"] = datetime.fromtimestamp(floor(timestamp_now + exp)).strftime("%Y/%m/%d at %H:%M:%S %Z")
        reasons.add(ban["reason"])

    builder = bans_builder(bans, list(reasons), list(remains))
    return render_template("bans.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))
