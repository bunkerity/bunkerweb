from datetime import datetime
from json import JSONDecodeError, dumps, loads
from math import floor
from time import time

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS

from app.routes.utils import get_redis_client, get_remain, handle_error, verify_data_in_form

bans = Blueprint("bans", __name__)


@bans.route("/bans", methods=["GET"])
@login_required
def bans_page():
    redis_client = get_redis_client()

    def get_load_data():
        try:
            data = loads(request.form["data"])
            assert isinstance(data, list)
            return data
        except BaseException:
            return handle_error("Data must be a list of dict", "bans", False, "exception")

    if request.method == "POST" and request.form["operation"] == "unban":
        data = get_load_data()

        for unban in data:
            try:
                unban = loads(unban.replace('"', '"').replace("'", '"'))
            except BaseException:
                flash(f"Invalid unban: {unban}, skipping it ...", "error")
                continue

            if "ip" not in unban:
                flash(f"Invalid unban: {unban}, skipping it ...", "error")
                continue

            if redis_client:
                if not redis_client.delete(f"bans_ip_{unban['ip']}"):
                    flash(f"Couldn't unban {unban['ip']} on redis", "error")

            resp = BW_INSTANCES_UTILS.unban(unban["ip"])
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
                current_time = datetime.now().astimezone()
                ban_end = (datetime.fromtimestamp(ban_end, tz=current_time.tzinfo) - current_time).total_seconds()

            if redis_client:
                ok = redis_client.set(f"bans_ip_{ban['ip']}", dumps({"reason": reason, "date": time()}))
                if not ok:
                    flash(f"Couldn't ban {ban['ip']} on redis", "error")
                redis_client.expire(f"bans_ip_{ban['ip']}", int(ban_end))

            resp = BW_INSTANCES_UTILS.ban(ban["ip"], ban_end, reason)
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
            bans.append({"ip": ip, "exp": exp} | loads(data))  # type: ignore
    instance_bans = BW_INSTANCES_UTILS.get_bans()

    # Prepare data
    timestamp_now = time()

    for ban in instance_bans:
        if not any(b["ip"] == ban["ip"] for b in bans):
            bans.append(ban)

    for ban in bans:
        exp = ban.pop("exp", 0)
        # Add remain
        remain = ("unknown", "unknown") if exp <= 0 else get_remain(exp)
        ban["remain"] = remain[0]
        # Convert stamp to date
        ban["start_date"] = datetime.fromtimestamp(floor(ban["date"])).astimezone().isoformat()
        ban["end_date"] = datetime.fromtimestamp(floor(timestamp_now + exp)).astimezone().isoformat()

    return render_template("bans.html", bans=bans)


@bans.route("/bans/ban", methods=["POST"])
@login_required
def bans_ban():
    verify_data_in_form(
        data={"bans": None},
        err_message="Missing bans parameter on /bans/ban.",
        redirect_url="bans",
        next=True,
    )
    bans = request.form["bans"]
    if not bans:
        return handle_error("No bans.", "bans", True)
    try:
        bans = loads(bans)
    except JSONDecodeError:
        return handle_error("Invalid bans parameter on /bans/ban.", "bans", True)

    redis_client = get_redis_client()
    for ban in bans:
        if not isinstance(ban, dict) or "ip" not in ban:
            flash(f"Invalid ban: {ban}, skipping it ...", "error")
            continue

        reason = ban.get("reason", "ui")
        try:
            ban_end = datetime.fromisoformat(ban["end_date"])
        except ValueError:
            flash(f"Invalid ban: {ban}, skipping it ...", "error")
            continue
        current_time = datetime.now().astimezone()
        ban_end = (ban_end - current_time).total_seconds()

        if redis_client:
            ok = redis_client.set(f"bans_ip_{ban['ip']}", dumps({"reason": reason, "date": time()}))
            if not ok:
                flash(f"Couldn't ban {ban['ip']} on redis", "error")
            redis_client.expire(f"bans_ip_{ban['ip']}", int(ban_end))

        resp = BW_INSTANCES_UTILS.ban(ban["ip"], ban_end, reason)
        if resp:
            flash(f"Couldn't ban {ban['ip']} on the following instances: {', '.join(resp)}", "error")
        else:
            flash(f"Successfully banned {ban['ip']}")

    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Banning {len(bans)} IP{'s' if len(bans) > 1 else ''}"))


@bans.route("/bans/unban", methods=["POST"])
@login_required
def bans_unban():
    verify_data_in_form(
        data={"ips": None},
        err_message="Missing bans parameter on /bans/unban.",
        redirect_url="bans",
        next=True,
    )
    unbans = request.form["ips"]
    if not unbans:
        return handle_error("No bans.", "ips", True)
    try:
        unbans = loads(unbans)
    except JSONDecodeError:
        return handle_error("Invalid ips parameter on /bans/unban.", "bans", True)

    redis_client = get_redis_client()
    for unban in unbans:
        if "ip" not in unban:
            flash(f"Invalid unban: {unban}, skipping it ...", "error")
            continue

        if redis_client:
            if not redis_client.delete(f"bans_ip_{unban['ip']}"):
                flash(f"Couldn't unban {unban['ip']} on redis", "error")

        resp = BW_INSTANCES_UTILS.unban(unban["ip"])
        if resp:
            flash(f"Couldn't unban {unban['ip']} on the following instances: {', '.join(resp)}", "error")
        else:
            flash(f"Successfully unbanned {unban['ip']}")

    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Unbanning {len(unbans)} IP{'s' if len(unbans) > 1 else ''}"))
