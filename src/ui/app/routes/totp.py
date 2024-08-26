from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.dependencies import DB
from app.models.totp import totp as TOTP
from app.routes.utils import handle_error, verify_data_in_form

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
            DB.use_ui_user_recovery_code(current_user.get_id(), recovery_code)

        session["totp_validated"] = True
        redirect(url_for("loading", next=request.form.get("next") or url_for("home.home_page"), message="Validating TOTP token."))

    if not bool(current_user.totp_secret) or session.get("totp_validated", False):
        return redirect(url_for("home.home_page"))

    return render_template("totp.html")
