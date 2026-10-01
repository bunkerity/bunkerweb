"""Let's Encrypt UI hooks backed exclusively by the control-plane API."""

from contextlib import suppress
from time import time
from typing import Dict, List

from flask import request, session, url_for
from markupsafe import Markup, escape

COLUMNS_PREFERENCES_DEFAULTS = {
    "3": True,
    "4": True,
    "5": True,
    "6": True,
    "7": True,
    "8": True,
    "9": False,
    "10": False,
    "11": True,
}

_ORPHAN_CHECK_INTERVAL_SECONDS = 60
_ORPHAN_CHECK_LAST_KEY = "_le_orphan_check_at"
_ORPHAN_NOTIFIED_KEY = "_le_orphan_notified"


def _detect_orphans_from_api() -> List[Dict[str, str]]:
    try:
        from app.dependencies import API_CLIENT  # type: ignore

        return [orphan for orphan in API_CLIENT.get_letsencrypt_orphans() if isinstance(orphan, dict)]
    except Exception:
        return []


def _flash_new_orphans(orphans: List[Dict[str, str]]) -> None:
    try:
        from app.utils import flash  # type: ignore
    except Exception:
        return

    try:
        from app.i18n import translated  # type: ignore
    except Exception:

        def translated(*_args, **_kwargs):  # type: ignore
            return None

    notified = set(session.get(_ORPHAN_NOTIFIED_KEY, []))
    current = {orphan.get("cert_name", "") for orphan in orphans if orphan.get("cert_name")}
    for orphan in orphans:
        cert_name = orphan.get("cert_name", "")
        if not cert_name or cert_name in notified:
            continue
        safe_cert = escape(cert_name)
        safe_account = escape(orphan.get("account", ""))
        certificates_url = escape(url_for("certificates.certificates_page"))
        link_text = translated("letsencrypt.flash.open_certificates_to_inspect") or "Open Certificates to inspect"
        # `flash()` (`app/utils.py`) escapes any plain `str` it receives, which would turn the
        # `<strong>`/`<code>`/`<a>` markup below into visible text. `safe_cert`/`safe_account`/
        # `certificates_url` are already escaped, so wrapping the finished text in `Markup(...)`
        # marks it trusted without escaping it a second time.
        text = translated(
            "letsencrypt.flash.orphan_certificate",
            cert_name=safe_cert,
            account=safe_account,
            certificates_url=certificates_url,
            link_text=link_text,
        ) or (
            f"Let's Encrypt: orphan certificate <strong>{safe_cert}</strong> "
            f"references missing ACME account <code>{safe_account}</code>. "
            "Renewals are blocked until the provider state is repaired. "
            f'<a href="{certificates_url}">{link_text}</a>.'
        )
        with suppress(Exception):
            flash(Markup(text), "warning", save=True)

    if current != notified:
        session[_ORPHAN_NOTIFIED_KEY] = list(current)
        session.modified = True


def context_processor():
    if request.path.startswith(("/check", "/setup", "/loading", "/login", "/totp", "/logout")):
        return None

    data = {"columns_preferences_defaults_letsencrypt": COLUMNS_PREFERENCES_DEFAULTS}
    with suppress(Exception):
        now = time()
        if now - session.get(_ORPHAN_CHECK_LAST_KEY, 0) >= _ORPHAN_CHECK_INTERVAL_SECONDS:
            session[_ORPHAN_CHECK_LAST_KEY] = now
            session.modified = True
            orphans = _detect_orphans_from_api()
            if orphans or session.get(_ORPHAN_NOTIFIED_KEY):
                _flash_new_orphans(orphans)
    return data
