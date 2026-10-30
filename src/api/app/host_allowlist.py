"""API_ALLOWED_HOSTS wildcard validation (leaf module, no heavy imports — unit-testable)."""


def invalid_host_patterns(hosts):
    """Return entries Starlette's TrustedHostMiddleware would reject (no "*" past index 0; a leading "*" must be "*" or "*.").

    We validate here because Starlette enforces this with an assert that runs lazily on the first request (so a
    try/except around add_middleware can't catch it) and is stripped under `python -O`.
    """
    return [h for h in hosts if ("*" in h[1:]) or (h.startswith("*") and h != "*" and not h.startswith("*."))]
