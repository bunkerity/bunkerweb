from flask import request

# A request that went through BunkerWeb (or any proxy) gets the strict, host-locked cookie. One
# that reached the UI port directly over plain HTTP cannot hold a Secure cookie, so it gets a
# plain name; the two never overwrite each other and one worker can serve both at once.
PROXIED_COOKIE_NAME = "__Host-bw_ui_session"
DIRECT_COOKIE_NAME = "bw_ui_session"


def is_proxied_request() -> bool:
    # X-Forwarded-Proto is applied by ReverseProxied, so is_secure covers an HTTPS hop without XFF.
    return request.environ.get("HTTP_X_FORWARDED_FOR") is not None or request.is_secure


class PerRequestCookieMixin:
    """Choose the session cookie name and Secure flag per request instead of per worker.

    Flask-Session reads the name from the app config when it opens the session and calls the
    get_cookie_* hooks when it saves it, so both sides are overridden and always agree.
    """

    def get_cookie_name(self, app) -> str:
        return PROXIED_COOKIE_NAME if is_proxied_request() else DIRECT_COOKIE_NAME

    def get_cookie_secure(self, app) -> bool:
        return is_proxied_request()

    def get_cookie_domain(self, app) -> None:
        # A __Host- cookie must not carry a Domain attribute, and a host-only cookie is what we want either way.
        return None

    # ponytail: no SESSION_USE_SIGNER branch, the UI never enables it and Flask-Session deprecates it.
    def open_session(self, app, req):
        sid = req.cookies.get(self.get_cookie_name(app))
        if sid:
            data = self._retrieve_session_data(self._get_store_id(sid))
            if data is not None:
                return self.session_class(data, sid=sid)
        return self.session_class(sid=self._generate_sid(self.sid_length), permanent=self.permanent)


def use_per_request_cookie(interface) -> None:
    """Swap the interface's class for one that mixes in PerRequestCookieMixin, keeping its state (Redis client, fallback cache, patched methods)."""
    interface.__class__ = type(interface.__class__.__name__, (PerRequestCookieMixin, interface.__class__), {})
