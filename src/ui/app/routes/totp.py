from flask import Blueprint, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.models.totp import totp as TOTP
from app.routes.utils import flash, handle_error, verify_data_in_form
from app.utils import _sanitize_internal_next

totp = Blueprint("totp", __name__)


@totp.route("/totp", methods=["GET", "POST"])
@login_required
def totp_page():
    if request.method == "POST":
        verify_data_in_form(data={"totp_token": None}, err_message="No token provided on /totp.", redirect_url="totp")

        if not TOTP.verify_totp(request.form["totp_token"], user=current_user):
            recovery_code = TOTP.verify_recovery_code(request.form["totp_token"], user=current_user)
            if not recovery_code:
                return handle_error("The token is invalid.", "totp")
            flash(f"You've used one of your recovery codes. You have {len(current_user.list_recovery_codes)} left.")
            try:
                API_CLIENT.use_recovery_code(current_user.get_id(), recovery_code)
            except (ApiClientError, ApiUnavailableError):
                return handle_error("An error occurred while using the recovery code.", "totp")

        session["totp_validated"] = True
        try:
            safe_next = _sanitize_internal_next(request.form.get("next"), url_for("home.home_page"))
        except ValueError:
            safe_next = url_for("home.home_page")
        return redirect(url_for("loading", next=safe_next, message="Validating TOTP token."))

    if not bool(current_user.totp_secret) or session.get("totp_validated", False):
        return redirect(url_for("home.home_page"))

    return render_template("totp.html")
