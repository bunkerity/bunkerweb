"""Keep a refused modal form's input across the redirect that reports the refusal.

The modal forms of /instances, /groups and /certificates post natively and the route answers every
refusal with a flash and a redirect, so the page came back with the modal closed and everything
typed gone (QA-UI M22, M28). The route now stores what was posted with `keep_form`, the page's GET
hands it back with `take_form_retry`, and `static/js/components/form-retry.js` refills the form
tagged `data-form-retry="<form_id>"`, shows the error inside it and reopens its modal.

Server-side sessions only (redis / cachelib, main.py), so the size of a posted form is not a cookie
problem. File inputs are not in `request.form` and cannot be refilled by a page anyway.
"""

from typing import Any, Dict

from flask import request, session

SESSION_KEY = "form_retry"


def keep_form(form_id: str, error: str) -> None:
    fields: Dict[str, Any] = {}
    for key in request.form:
        if key == "csrf_token":
            continue
        values = request.form.getlist(key)
        fields[key] = values if len(values) > 1 else values[0]
    session[SESSION_KEY] = {"form": form_id, "error": error, "fields": fields}


def take_form_retry() -> Dict[str, Any]:
    """The kept form, once: a reload after it has been shown opens the page clean."""
    return session.pop(SESSION_KEY, None) or {}
