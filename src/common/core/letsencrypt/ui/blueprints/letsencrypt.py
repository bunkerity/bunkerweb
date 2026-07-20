"""Compatibility redirect for the retired direct-DB Let's Encrypt UI.

Certificate inventory and provider lifecycle operations now flow through the
central UI and the Let's Encrypt API extension. Keeping only this redirect
preserves old bookmarks without leaving broken mutation endpoints mounted in
the UI process, where direct database access is intentionally unavailable.
"""

from os.path import dirname

from flask import Blueprint, redirect, url_for
from flask_login import login_required

blueprint_path = dirname(__file__)

letsencrypt = Blueprint(
    "letsencrypt",
    __name__,
    static_folder=f"{blueprint_path}/static",
    template_folder=f"{blueprint_path}/templates",
)


@letsencrypt.route("/letsencrypt", methods=["GET"])
@login_required
def letsencrypt_page():
    return redirect(url_for("certificates.certificates_page"), code=302)
