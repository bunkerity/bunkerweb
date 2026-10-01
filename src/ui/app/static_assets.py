from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Optional

from flask import Flask, request
from werkzeug.security import safe_join

# A URL that changes with its content can be cached for as long as the browser cares to keep it.
VERSIONED_CACHE_CONTROL = "public, max-age=31536000, immutable"


@lru_cache(maxsize=2048)
def _fingerprint(path: str, mtime_ns: int, size: int) -> str:
    """Content hash of a static file. mtime and size are only the cache key: a dev edit or an
    upgrade changes them, so the file is hashed again, and a rebuild that touched nothing hashes
    the same."""
    return sha256(Path(path).read_bytes()).hexdigest()[:16]


def static_fingerprint(static_folder: str, filename: str) -> Optional[str]:
    """The fingerprint of `filename` under `static_folder`, or None when it is not a file (the
    `img/flags` base URL that JS completes, a typo) or escapes the folder -- on the response side
    `filename` is the client's."""
    joined = safe_join(static_folder, filename)
    if joined is None:
        return None
    path = Path(joined)
    try:
        stat = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    return _fingerprint(str(path), stat.st_mtime_ns, stat.st_size)


def version_static_urls(app: Flask) -> None:
    """Add `v=<content fingerprint>` to every URL built for the `static` endpoint, and cache by it.

    Without it `url_for('static', ...)` built the same URL across releases, so a browser kept
    running the previous release's page scripts against the new templates until its cache expired.

    The cache headers follow: the current fingerprint is cached for a year, since the URL moves
    with the content. Everything else is `no-cache` -- revalidated, answered 304 when unchanged.
    That covers the URLs this hook never sees: ES-module child imports (a relative `import`
    resolves without the parent's query), URLs completed in JS, and fingerprints of an older file.
    """

    @app.url_defaults
    def _add_static_version(endpoint, values):
        if endpoint != "static" or "v" in values or not app.static_folder:
            return
        fingerprint = static_fingerprint(app.static_folder, values.get("filename", ""))
        if fingerprint:
            values["v"] = fingerprint

    @app.after_request
    def _static_cache_control(response):
        if request.endpoint != "static":
            return response
        current = static_fingerprint(app.static_folder or "", (request.view_args or {}).get("filename", ""))
        if current and request.args.get("v") == current:
            response.headers["Cache-Control"] = VERSIONED_CACHE_CONTROL
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response
