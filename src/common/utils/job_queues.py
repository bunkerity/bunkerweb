#!/usr/bin/env python3
"""Single source of truth for job queue lane routing.

The API dispatches jobs and the worker consumes them, so both sides need the
same heavy/default split. This set used to be duplicated in `src/worker/app.py`
and `src/api/app/routers/jobs.py`, each carrying a comment asking the reader to
keep the two copies in sync by hand.
"""

# Long-running or resource-intensive jobs. They get their own lane so a certbot
# run or a blocklist download never starves the fast maintenance jobs.
#
# Not listed (they were in the old copies but can never be dispatched):
#   - certbot-auth / certbot-cleanup are certbot's own --manual-*-hook scripts,
#     spawned by certbot-new; neither is declared in any plugin.json.
#   - coreruleset-nightly is now a deprecation warning with no side effects and
#     is likewise declared nowhere.
HEAVY_JOBS = frozenset(
    {
        "backup-data",
        "bunkernet-data",
        "bunkernet-register",
        "certbot-new",
        "certbot-renew",
        "download-crs-plugins",
        "download-plugins",
        "download-pro-plugins",
        "push-configs",
    }
)


def queue_for(job_name: str) -> str:
    """Return the queue lane a job belongs to."""
    return "heavy" if job_name in HEAVY_JOBS else "default"
