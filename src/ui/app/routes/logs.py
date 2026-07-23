from contextlib import suppress
from itertools import islice
from os import cpu_count, getenv, listdir
from os.path import isabs, sep
from pathlib import Path
import json
import threading
import time

from flask import Blueprint, Response, render_template, request, send_file
from flask_login import login_required
from werkzeug.utils import secure_filename

logs = Blueprint("logs", __name__)

LOGS_PATH = Path(sep, "var", "log", "bunkerweb")
PAGE_SIZE = 10000

# --- SSE (live-follow) tuning ---
REFRESH_TAIL_BYTES = 2 * 1024 * 1024  # cap the initial/rotated SSE payload to the last 2 MiB
STREAM_MAX_SECONDS = 900  # bound a follow session; the client auto-reconnects and resumes via Last-Event-ID
MAX_MULTI_SOURCES = 20  # cap the merged live-tail fan-in so one stream can't poll unbounded files
# Cap concurrent live-follow streams PER WORKER so they can't exhaust the gthread
# pool (effective global ceiling = gunicorn workers * _STREAM_LIMIT). The default
# mirrors gunicorn.conf.py's threads default (MAX_WORKERS*2) when MAX_THREADS is unset.
try:
    _default_threads = str(max(1, (cpu_count() or 1) - 1) * 2)
    _STREAM_LIMIT = max(1, int(getenv("MAX_THREADS", _default_threads)) - 1)
except (ValueError, TypeError):
    _STREAM_LIMIT = 3
_stream_lock = threading.Lock()
_active_streams = 0


def _list_log_files():
    """Return {'main': [...], 'letsencrypt': [...]} of the available *.log files."""
    letsencrypt_path = LOGS_PATH / "letsencrypt"
    files = {"main": [], "letsencrypt": []}

    if LOGS_PATH.is_dir() and listdir(LOGS_PATH):
        for file in LOGS_PATH.glob("*.log"):
            if file.is_file():
                files["main"].append(file.name)
        files["main"].sort()

    if letsencrypt_path.is_dir() and listdir(letsencrypt_path):
        letsencrypt_files = [file.name for file in letsencrypt_path.glob("*.log*") if file.is_file()]

        # Sort letsencrypt files with proper numerical ordering (.log, .log.1, .log.2, ...)
        def sort_key(filename):
            if filename.endswith(".log"):
                return (0, filename)
            with suppress(ValueError, IndexError):
                parts = filename.split(".log.")
                if len(parts) == 2:
                    return (int(parts[1]), filename)
            return (999999, filename)

        letsencrypt_files.sort(key=sort_key)
        files["letsencrypt"] = [f"letsencrypt_{name}" for name in letsencrypt_files]

    return files


def _resolve_log_path(current_file, files):
    """Validate `current_file` against the listing and return its Path, or None.

    Guards against path traversal: the name must be one of the listed files and
    must not be absolute or contain `..`.
    """
    all_files = files["main"] + files["letsencrypt"]
    if not current_file or current_file not in all_files:
        return None
    if isabs(current_file) or ".." in current_file:
        return None
    if current_file.startswith("letsencrypt_"):
        # Strip only the prefix (not every occurrence) before joining.
        return LOGS_PATH.joinpath("letsencrypt", current_file[len("letsencrypt_") :])  # noqa: E203
    return LOGS_PATH.joinpath(current_file)


@logs.route("/logs", methods=["GET"])
@login_required
def logs_page():
    files = _list_log_files()
    all_files = files["main"] + files["letsencrypt"]

    current_file = secure_filename(request.args.get("file", ""))

    if current_file and current_file not in all_files:
        return Response("No such file", 404)

    if isabs(current_file) or ".." in current_file:
        return Response("Invalid file path", 400)

    raw_logs = (
        "Select a log file to view its contents"
        if all_files
        else "There are no log files to display, check the documentation for more information on how to enable logging"
    )
    page_num = 1
    page = 1
    file_meta = None

    if current_file:
        file_path = _resolve_log_path(current_file, files)
        if file_path is None or not file_path.is_file():
            return Response("No such file", 404)

        # Count lines without holding the whole file in memory (avoids OOM on
        # very large logs — only one line is resident at a time).
        total_lines = 0
        with file_path.open(encoding="utf-8", errors="replace") as f:
            for _ in f:
                total_lines += 1
        # Ceil division so an exact multiple of PAGE_SIZE doesn't add a spurious
        # trailing empty page (which would be the default "latest" view).
        page_num = max(1, -(-total_lines // PAGE_SIZE))

        # Default to the latest page; clamp anything out of range.
        try:
            page = int(request.args.get("page", 0)) or page_num
        except (TypeError, ValueError):
            page = page_num
        page = max(1, min(page, page_num))

        # Read only the requested page's slice (O(page) memory, not O(file)).
        start = (page - 1) * PAGE_SIZE
        with file_path.open(encoding="utf-8", errors="replace") as f:
            raw_logs = "".join(islice(f, start, start + PAGE_SIZE)).rstrip("\n")

        stat = file_path.stat()
        file_meta = {"size": stat.st_size, "lines": total_lines, "mtime": stat.st_mtime}

    return render_template(
        "logs.html",
        logs=raw_logs,
        files=files,
        current_file=current_file,
        current_page=page if current_file else page_num,
        page_num=page_num,
        file_meta=file_meta,
    )


@logs.route("/logs/download", methods=["GET"])
@login_required
def download_log():
    files = _list_log_files()
    current_file = secure_filename(request.args.get("file", ""))

    file_path = _resolve_log_path(current_file, files)
    if file_path is None or not file_path.is_file():
        return Response("No such file", 404)

    return send_file(
        file_path,
        mimetype="text/plain",
        as_attachment=True,
        download_name=current_file.removeprefix("letsencrypt_"),
        max_age=0,
    )


def _read_tail(file_path, size):
    """Read the last REFRESH_TAIL_BYTES of a file, dropping a partial leading line.

    Bounds the initial/rotated SSE payload (and the server-side memory spike) on
    very large logs instead of reading the whole file.
    """
    start = max(0, size - REFRESH_TAIL_BYTES)
    with file_path.open(encoding="utf-8", errors="replace") as f:
        f.seek(start)
        data = f.read()
    if start > 0:
        nl = data.find("\n")
        data = data[nl + 1 :] if nl != -1 else data  # noqa: E203
    return data


@logs.route("/logs/stream", methods=["GET"])
@login_required
def stream_logs():
    # Same allowlist gate as /logs and /logs/download — the requested file must
    # be one of the listed *.log files (not just anything under the log dir).
    files = _list_log_files()
    current_file = secure_filename(request.args.get("file", ""))

    file_path = _resolve_log_path(current_file, files)
    if file_path is None or not file_path.is_file():
        return Response("No such file", 404)

    # Resume offset from a reconnecting EventSource (the browser replays the last
    # `id:` we sent as the Last-Event-ID header) — lets us resume without re-sending.
    resume_from = None
    last_event_id = request.headers.get("Last-Event-ID")
    if last_event_id:
        with suppress(TypeError, ValueError):
            resume_from = max(0, int(last_event_id))

    def generate():
        global _active_streams
        # Bound concurrent streams so live-follow can't exhaust the gthread pool.
        with _stream_lock:
            if _active_streams >= _STREAM_LIMIT:
                over_limit = True
            else:
                _active_streams += 1
                over_limit = False
        if over_limit:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Too many active log streams, please retry'})}\n\n"
            return

        started = time.monotonic()
        heartbeat_counter = 0
        try:
            yield "retry: 5000\n\n"  # explicit reconnect interval

            last_size = 0
            last_mtime = 0
            with suppress(OSError):
                last_size = file_path.stat().st_size

            # Resume from the client's offset if still valid, else send a bounded tail.
            if resume_from is not None and resume_from <= last_size:
                with file_path.open(encoding="utf-8", errors="replace") as f:
                    f.seek(resume_from)
                    new_content = f.read()
                if new_content:
                    yield f"id: {last_size}\ndata: {json.dumps({'type': 'append', 'content': new_content, 'size': last_size})}\n\n"
            else:
                content = _read_tail(file_path, last_size)
                yield f"id: {last_size}\ndata: {json.dumps({'type': 'refresh', 'content': content, 'size': last_size})}\n\n"
            with suppress(OSError):
                last_mtime = file_path.stat().st_mtime

            while True:
                # Bound the session so a forgotten tab releases its thread; the
                # client reconnects and resumes from the last id (no gap).
                if time.monotonic() - started > STREAM_MAX_SECONDS:
                    break

                content_sent = False
                try:
                    current_stat = file_path.stat()
                    current_size = current_stat.st_size
                    current_mtime = current_stat.st_mtime

                    if current_mtime != last_mtime or current_size != last_size:
                        if current_size < last_size:  # rotated / truncated
                            content = _read_tail(file_path, current_size)
                            yield f"id: {current_size}\ndata: {json.dumps({'type': 'rotated', 'content': content, 'size': current_size})}\n\n"
                            last_size = current_size
                            content_sent = True
                        elif current_size > last_size:  # appended
                            with file_path.open(encoding="utf-8", errors="replace") as f:
                                f.seek(last_size)
                                new_content = f.read()
                            yield f"id: {current_size}\ndata: {json.dumps({'type': 'append', 'content': new_content, 'size': current_size})}\n\n"
                            last_size = current_size
                            content_sent = True

                        last_mtime = current_mtime
                        heartbeat_counter = 0

                    # Comment-style keep-alive (~10s): resets the proxy read timeout
                    # without firing the client's onmessage (EventSource ignores comments).
                    heartbeat_counter += 1
                    if heartbeat_counter >= 10 and not content_sent:
                        yield ": keep-alive\n\n"
                        heartbeat_counter = 0

                except FileNotFoundError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'File was deleted'})}\n\n"
                    break
                except Exception:
                    # Don't leak internal paths / exception text to the client.
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Error reading log file'})}\n\n"
                    break

                time.sleep(1)
        finally:
            with _stream_lock:
                _active_streams -= 1

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable proxy buffering so events flush in real time behind nginx
            # (BunkerWeb's reverse proxy defaults to proxy_buffering on).
            "X-Accel-Buffering": "no",
        },
    )


@logs.route("/logs/stream/multi", methods=["GET"])
@login_required
def stream_multi():
    """Server-merged live-tail of several log files over ONE EventSource.

    The live dashboard tails N sources at once. Browsers cap concurrent
    connections per host (~6) and each SSE eats a gthread slot, so N separate
    /logs/stream connections are non-viable — one merged stream fans in here and
    takes a single ``_active_streams`` slot. Every source name is validated
    through the same ``_resolve_log_path`` allowlist as the single-file routes.

    Frames are ``{"type": "refresh"|"append"|"rotated", "source": name,
    "content": raw}``. No server-side classification (the client owns level
    detection). Reconnect re-sends a bounded tail per source (no multi-offset
    Last-Event-ID in v1); the client re-backfills on ``onopen``.
    """
    files = _list_log_files()

    # Parse + validate the requested sources, preserving order and de-duping.
    sources = []
    seen = set()
    for raw_name in request.args.get("sources", "").split(","):
        name = secure_filename(raw_name.strip())
        if not name or name in seen:
            continue
        file_path = _resolve_log_path(name, files)
        if file_path is None or not file_path.is_file():
            continue  # unknown / traversal / missing — silently drop, never leak
        seen.add(name)
        sources.append((name, file_path))
        if len(sources) >= MAX_MULTI_SOURCES:
            break

    if not sources:
        return Response("No such file", 404)

    def generate():
        global _active_streams
        with _stream_lock:
            if _active_streams >= _STREAM_LIMIT:
                over_limit = True
            else:
                _active_streams += 1
                over_limit = False
        if over_limit:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Too many active log streams, please retry'})}\n\n"
            return

        started = time.monotonic()
        heartbeat_counter = 0
        try:
            yield "retry: 5000\n\n"  # explicit reconnect interval

            # Per-source [path, last_size, last_mtime]; seed with a bounded tail
            # emitted as a `refresh` frame (the client backfills + sorts these).
            state = {}
            for name, file_path in sources:
                size = 0
                mtime = 0
                with suppress(OSError):
                    stat = file_path.stat()
                    size = stat.st_size
                    mtime = stat.st_mtime
                content = ""
                with suppress(OSError):
                    content = _read_tail(file_path, size)
                state[name] = [file_path, size, mtime]
                yield f"data: {json.dumps({'type': 'refresh', 'source': name, 'content': content})}\n\n"

            while True:
                # Bound the session so a forgotten tab releases its thread; the
                # client reconnects (retry) and re-backfills from onopen.
                if time.monotonic() - started > STREAM_MAX_SECONDS:
                    break

                content_sent = False
                for name, file_path in sources:
                    st = state[name]
                    last_size, last_mtime = st[1], st[2]
                    try:
                        current_stat = file_path.stat()
                    except OSError:
                        # Temporarily gone (rotation window / deleted) — skip this
                        # tick and retry; don't tear the whole merged stream down.
                        continue
                    current_size = current_stat.st_size
                    current_mtime = current_stat.st_mtime
                    if current_mtime == last_mtime and current_size == last_size:
                        continue

                    if current_size < last_size:  # rotated / truncated
                        content = ""
                        with suppress(OSError):
                            content = _read_tail(file_path, current_size)
                        yield f"data: {json.dumps({'type': 'rotated', 'source': name, 'content': content})}\n\n"
                        content_sent = True
                    elif current_size > last_size:  # appended
                        new_content = ""
                        with suppress(OSError):
                            with file_path.open(encoding="utf-8", errors="replace") as f:
                                f.seek(last_size)
                                new_content = f.read()
                        if new_content:
                            yield f"data: {json.dumps({'type': 'append', 'source': name, 'content': new_content})}\n\n"
                            content_sent = True
                    st[1] = current_size
                    st[2] = current_mtime

                # Comment-style keep-alive (~10s): resets the proxy read timeout
                # without firing the client's onmessage (EventSource ignores comments).
                heartbeat_counter = 0 if content_sent else heartbeat_counter + 1
                if heartbeat_counter >= 10:
                    yield ": keep-alive\n\n"
                    heartbeat_counter = 0

                time.sleep(1)
        finally:
            with _stream_lock:
                _active_streams -= 1

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
