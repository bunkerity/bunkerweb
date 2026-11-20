"""/logs: the file allowlist, pagination, download and the live-follow event stream."""

import json

import pytest


@pytest.fixture
def logs(h, tmp_path, monkeypatch):
    module = h.routes.logs
    root = tmp_path / "bunkerweb"
    (root / "letsencrypt").mkdir(parents=True)
    monkeypatch.setattr(module, "LOGS_PATH", root)
    monkeypatch.setattr(module, "_LINECOUNT_CACHE", {})
    monkeypatch.setattr(module, "root", root, raising=False)
    return module


def _write(logs, name, text):
    path = logs.root / name
    path.write_text(text)
    return path


def test_page_without_any_log_file_explains_how_to_enable_logging(h, logs):
    h.client().get("/logs")

    context = h.renders[-1][1]
    assert "There are no log files to display" in context["logs"]
    assert context["files"] == {"main": [], "letsencrypt": []}


def test_page_lists_main_and_letsencrypt_files_in_order(h, logs):
    _write(logs, "ui.log", "x\n")
    _write(logs, "scheduler.log", "x\n")
    for name in ("letsencrypt.log.10", "letsencrypt.log", "letsencrypt.log.2", "letsencrypt.log.zip"):
        (logs.root / "letsencrypt" / name).write_text("x")

    h.client().get("/logs")

    context = h.renders[-1][1]
    assert context["logs"] == "Select a log file to view its contents"
    assert context["files"]["main"] == ["scheduler.log", "ui.log"]
    assert context["files"]["letsencrypt"] == [
        "letsencrypt_letsencrypt.log",
        "letsencrypt_letsencrypt.log.2",
        "letsencrypt_letsencrypt.log.10",
        "letsencrypt_letsencrypt.log.zip",
    ]


def test_page_shows_the_latest_page_of_a_file_with_its_metadata(h, logs, monkeypatch):
    monkeypatch.setattr(logs, "PAGE_SIZE", 3)
    _write(logs, "ui.log", "".join(f"line {n}\n" for n in range(1, 8)))

    h.client().get("/logs?file=ui.log")

    context = h.renders[-1][1]
    assert context["logs"] == "line 7" and context["page_num"] == 3 and context["current_page"] == 3
    assert context["file_meta"]["lines"] == 7


@pytest.mark.parametrize(
    "page, expected", [("1", "line 1\nline 2\nline 3"), ("2", "line 4\nline 5\nline 6"), ("99", "line 7"), ("junk", "line 7"), ("-4", "line 1\nline 2\nline 3")]
)
def test_page_parameter_is_clamped(h, logs, monkeypatch, page, expected):
    monkeypatch.setattr(logs, "PAGE_SIZE", 3)
    _write(logs, "ui.log", "".join(f"line {n}\n" for n in range(1, 8)))

    h.client().get(f"/logs?file=ui.log&page={page}")

    assert h.renders[-1][1]["logs"] == expected


def test_an_exact_multiple_of_the_page_size_has_no_empty_last_page(h, logs, monkeypatch):
    monkeypatch.setattr(logs, "PAGE_SIZE", 2)
    _write(logs, "ui.log", "a\nb\nc\nd\n")

    h.client().get("/logs?file=ui.log")

    assert h.renders[-1][1]["page_num"] == 2 and h.renders[-1][1]["logs"] == "c\nd"


def test_the_line_count_cache_is_keyed_on_file_identity(h, logs):
    path = _write(logs, "ui.log", "a\nb\n")
    client = h.client()
    client.get("/logs?file=ui.log")
    assert h.renders[-1][1]["file_meta"]["lines"] == 2

    path.write_text("a\nb\nc\nd\ne\n")
    client.get("/logs?file=ui.log")

    assert h.renders[-1][1]["file_meta"]["lines"] == 5


@pytest.mark.parametrize("file", ["missing.log", "..%2F..%2Fetc%2Fpasswd", "/etc/passwd", "letsencrypt_nothing.log"])
def test_page_refuses_a_file_that_is_not_listed(h, logs, file):
    _write(logs, "ui.log", "secret\n")

    response = h.client().get(f"/logs?file={file}")

    assert response.status_code == 404 and h.renders == []


def test_download_serves_a_listed_file_as_plain_text(h, logs):
    _write(logs, "ui.log", "hello\n")
    (logs.root / "letsencrypt" / "letsencrypt.log").write_text("le\n")
    client = h.client()

    plain = client.get("/logs/download?file=ui.log")
    le = client.get("/logs/download?file=letsencrypt_letsencrypt.log")

    assert plain.get_data() == b"hello\n" and plain.mimetype == "text/plain"
    assert "filename=ui.log" in plain.headers["Content-Disposition"]
    assert le.get_data() == b"le\n" and "filename=letsencrypt.log" in le.headers["Content-Disposition"]


@pytest.mark.parametrize("file", ["nope.log", "../x", "", "letsencrypt_"])
def test_download_refuses_unlisted_files(h, logs, file):
    _write(logs, "ui.log", "x")

    assert h.client().get("/logs/download", query_string={"file": file}).status_code == 404


def test_stream_refuses_unlisted_files(h, logs):
    assert h.client().get("/logs/stream?file=nope.log").status_code == 404


def _events(chunks):
    out = []
    for chunk in chunks:
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        for line in text.splitlines():
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
    return out


def test_stream_sends_a_refresh_then_appended_bytes(h, logs, monkeypatch):
    monkeypatch.setattr(logs.time, "sleep", lambda seconds: None)
    path = _write(logs, "ui.log", "first\n")
    response = h.client().get("/logs/stream?file=ui.log")
    chunks = response.response

    retry, refresh = next(chunks), next(chunks)
    path.write_text("first\nsecond\n")
    append = next(chunks)
    response.close()

    assert retry == "retry: 5000\n\n" or retry == b"retry: 5000\n\n"
    assert _events([refresh, append]) == [{"type": "refresh", "content": "first\n", "size": 6}, {"type": "append", "content": "second\n", "size": 13}]
    assert response.mimetype == "text/event-stream" and response.headers["X-Accel-Buffering"] == "no"


def test_stream_resumes_from_last_event_id(h, logs, monkeypatch):
    monkeypatch.setattr(logs.time, "sleep", lambda seconds: None)
    _write(logs, "ui.log", "first\nsecond\n")
    response = h.client().get("/logs/stream?file=ui.log", headers={"Last-Event-ID": "6"})
    chunks = response.response

    next(chunks)
    event = _events([next(chunks)])[0]
    response.close()

    assert event == {"type": "append", "content": "second\n", "size": 13}


def test_stream_reports_a_rotated_file(h, logs, monkeypatch):
    monkeypatch.setattr(logs.time, "sleep", lambda seconds: None)
    path = _write(logs, "ui.log", "a long first line\n")
    response = h.client().get("/logs/stream?file=ui.log")
    chunks = response.response
    next(chunks), next(chunks)

    path.write_text("new\n")
    event = _events([next(chunks)])[0]
    response.close()

    assert event == {"type": "rotated", "content": "new\n", "size": 4}


def test_stream_reports_a_deleted_file(h, logs, monkeypatch):
    monkeypatch.setattr(logs.time, "sleep", lambda seconds: None)
    path = _write(logs, "ui.log", "a\n")
    response = h.client().get("/logs/stream?file=ui.log")
    chunks = response.response
    next(chunks), next(chunks)

    path.unlink()
    event = _events([next(chunks)])[0]
    response.close()

    assert event == {"type": "error", "message": "File was deleted"}


def test_stream_ends_after_the_session_bound_and_releases_its_slot(h, logs, monkeypatch):
    monkeypatch.setattr(logs.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(logs, "STREAM_MAX_SECONDS", -1)
    _write(logs, "ui.log", "a\n")
    before = logs._active_streams

    response = h.client().get("/logs/stream?file=ui.log")
    body = response.get_data(as_text=True)

    assert '"type": "refresh"' in body
    assert logs._active_streams == before


def test_stream_over_the_concurrency_limit_is_told_to_retry(h, logs, monkeypatch):
    monkeypatch.setattr(logs, "_active_streams", logs._STREAM_LIMIT)
    _write(logs, "ui.log", "a\n")

    body = h.client().get("/logs/stream?file=ui.log").get_data(as_text=True)

    assert "Too many active log streams" in body and "refresh" not in body
