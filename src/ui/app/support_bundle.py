from collections import deque
from datetime import datetime, timezone
from json import dumps
from logging import Handler
from operator import itemgetter
from os import getpid, stat
from os.path import basename, join
from re import compile as re_compile
from stat import S_ISREG
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from support_common import (  # type: ignore  # noqa: F401  (build_environment, build_plugins_report and read_plugin_version are re-exported)
    FILE_TAIL_CAP,
    LOG_DIR,
    TOTAL_CAP,
    TRUNCATED_MARK,
    Anonymizer,
    BundleZip,
    build_environment,
    build_plugins_report,
    cut_text,
    read_log_tail,
    read_plugin_version,
    valid_log_path,
)

RECORD_CAP = 4096
RING_CAP = 1024 * 1024
ERROR_BLOCKS = 20
ERROR_BLOCK_LINES = 200
LOG_CONDITIONS = {
    "error log": "CAPTURE_OUTPUT=yes or LOG_TYPES contains file with a valid LOG_FILE_PATH",
    "access log": "CAPTURE_OUTPUT=yes or LOG_TYPES contains file with a valid LOG_FILE_PATH",
    "app logger": "LOG_TYPES contains file with a valid LOG_FILE_PATH",
}
STDERR_COMMANDS = ("docker logs <ui container>", "kubectl logs <ui pod>", "journalctl -u bunkerweb-ui")


class RingBufferHandler(Handler):
    """Keeps the most recent formatted log records of this worker, bounded in bytes at ingestion."""

    def __init__(self, record_cap: int = RECORD_CAP, total_cap: int = RING_CAP):
        super().__init__()
        self.record_cap = record_cap
        self.total_cap = total_cap
        self.started = datetime.now(timezone.utc)
        self._records: deque = deque()
        self._size = 0
        self._cut = 0
        self._evicted = 0
        self._guard = Anonymizer()

    def emit(self, record) -> None:
        try:
            text = self.format(record)
            if len(text) * 4 > self.record_cap and len(text.encode("utf-8")) > self.record_cap:
                # Redact before cutting: the domain-less anonymizer still removes every credential form
                text, _ = cut_text(self._guard.redact(text), self.record_cap)
                self._cut += 1
            size = len(text.encode("utf-8"))
            self._records.append((text, size))
            self._size += size
            while self._size > self.total_cap and self._records:
                self._size -= self._records.popleft()[1]
                self._evicted += 1
        except Exception:
            self.handleError(record)

    def snapshot(self) -> Dict[str, Any]:
        self.acquire()
        try:
            return {
                "pid": getpid(),
                "started": self.started.isoformat(),
                "records": [text for text, _ in self._records],
                "bytes": self._size,
                "records_cut": self._cut,
                "records_evicted": self._evicted,
            }
        finally:
            self.release()


RING_HANDLER = RingBufferHandler()


def _file_outputs(environ: Mapping[str, str], default_name: str) -> List[Tuple[str, str]]:
    """The files one UI process writes, mirroring logger.py and the gunicorn config (gunicorn.conf.py, tmp-gunicorn.conf.py)."""
    log_types = environ.get("LOG_TYPES", "stderr").split()
    capture = environ.get("CAPTURE_OUTPUT", "no").lower() == "yes"
    scheduler_default = join(LOG_DIR, "scheduler.log") if environ.get("SCHEDULER_LOG_TO_FILE", "no") == "yes" else ""
    app_path = environ.get("LOG_FILE_PATH", scheduler_default).strip()
    app_file = "file" in log_types and valid_log_path(app_path)

    outputs = []
    if capture or app_file:
        errorlog = environ.get("LOG_FILE_PATH", join(LOG_DIR, default_name))
        outputs.extend(((errorlog, "error log"), (f"{errorlog.rsplit('.', 1)[0]}-access.log", "access log")))
    if app_file:
        outputs.append((app_path, "app logger"))
    return outputs


def log_sources(environ: Mapping[str, str], integration: str) -> List[Dict[str, Any]]:
    """Log files the main and temporary UI write, deduplicated by path.

    Containers unset LOG_FILE_PATH for the temporary UI (entrypoint.sh), Linux keeps it (bunkerweb-ui.sh), so there both share the main UI's files.
    """
    tmp_environ = {key: value for key, value in environ.items() if not (integration != "Linux" and key == "LOG_FILE_PATH")}
    sources: Dict[str, Dict[str, Any]] = {}
    for process, process_environ, default_name in (("main UI", environ, "ui.log"), ("temporary UI", tmp_environ, "tmp-ui.log")):
        for path, role in _file_outputs(process_environ, default_name):
            sources.setdefault(path, {"path": path, "writers": []})["writers"].append(f"{process} {role}")
    return list(sources.values())


_RECORD_START = re_compile(r"^\[\d{4}-\d{2}-\d{2} ")
_ERROR_MARK = re_compile(r"\[(?:❌|🚨|ERROR|CRITICAL)\]")


def error_blocks(text: str, max_lines: int = ERROR_BLOCK_LINES) -> Tuple[List[List[str]], int]:
    """ERROR or traceback blocks of already redacted text, each cut at max_lines. Returns the blocks and the number of cut blocks."""
    blocks: List[List[str]] = []
    current: Optional[List[str]] = None
    cut = 0
    for line in text.splitlines():
        if _RECORD_START.match(line):
            current = [line] if _ERROR_MARK.search(line) else None
            if current is not None:
                blocks.append(current)
        elif line.startswith("Traceback (most recent call last)") and current is None:
            current = [line]
            blocks.append(current)
        elif current is not None:
            if len(current) < max_lines:
                current.append(line)
            elif len(current) == max_lines:
                current.append(TRUNCATED_MARK.strip())
                cut += 1
    return blocks, cut


def build_support_bundle(
    *,
    domains: Iterable[str],
    environ: Mapping[str, str],
    integration: str,
    ring: Mapping[str, Any],
    plugins: Mapping[str, Any],
    environment: Mapping[str, Any],
    now: Optional[datetime] = None,
    file_cap: int = FILE_TAIL_CAP,
    total_cap: int = TOTAL_CAP,
) -> bytes:
    """Build the zip of the Web UI support bundle from already collected, allow-listed data."""
    anonymizer = Anonymizer(domains)
    out = BundleZip(total_cap)
    unavailable: List[Dict[str, str]] = []
    source_report = []
    redacted_texts: List[Tuple[str, str]] = []
    used_names = set()

    for source in log_sources(environ, integration):
        path = source["path"]
        conditions = sorted({LOG_CONDITIONS[writer.split(" UI ", 1)[1]] for writer in source["writers"]})
        report = {"path": path, "writers": source["writers"], "conditions": conditions}
        source_report.append(report)
        if not valid_log_path(path):
            report["status"] = "skipped: path rejected by the log path guard"
            continue
        try:
            if not S_ISREG(stat(path).st_mode):
                report["status"] = "skipped: not a regular file (stream or device)"
                continue
            text, size = read_log_tail(path, file_cap)
        except FileNotFoundError:
            report["status"] = "not found"
            continue
        except OSError as exc:
            report["status"] = f"unreadable: {exc.strerror or type(exc).__name__}"
            continue
        text = anonymizer.redact(text)
        name = f"logs/{basename(path)}"
        if name in used_names:
            name = f"logs/{len(used_names)}-{basename(path)}"
        used_names.add(name)
        report.update(
            {"status": "included", "file_bytes": size, "included_bytes": len(text.encode("utf-8")), "cut_to_last_bytes": file_cap if size > file_cap else None}
        )
        out.add(name, text, note=f"{path} ({', '.join(source['writers'])})")
        redacted_texts.append((name, text))

    ring_records = [anonymizer.redact(record) for record in ring.get("records", [])]
    if ring_records:
        header = f"# worker pid {ring.get('pid')}, ring started {ring.get('started')}, other workers are not included\n"
        ring_text = header + "\n".join(ring_records) + "\n"
        out.add("logs/ui-recent.log", ring_text, note="in-process ring buffer of the worker serving the request")
        redacted_texts.append(("logs/ui-recent.log", ring_text))
    else:
        unavailable.append({"item": "logs/ui-recent.log", "reason": "the ring buffer of this worker is empty"})
    if not any(item.get("status") == "included" for item in source_report):
        unavailable.append({"item": "log files", "reason": "no UI log file found; output goes to stderr, collect it with: " + "; ".join(STDERR_COMMANDS)})

    blocks_seen = set()
    blocks: List[Tuple[str, str, List[str]]] = []
    blocks_cut = 0
    for name, text in redacted_texts:
        found, cut = error_blocks(text)
        blocks_cut += cut
        for block in found:
            key = tuple(block)
            if key not in blocks_seen:
                blocks_seen.add(key)
                blocks.append((block[0][:21] if _RECORD_START.match(block[0]) else "", name, block))
    blocks.sort(key=itemgetter(0))
    kept = blocks[-ERROR_BLOCKS:]
    out.add("errors.txt", "\n\n".join(f"--- {name} ---\n" + "\n".join(block) for _, name, block in kept) + ("\n" if kept else ""))

    out.add("plugins.json", dumps(plugins, indent=2, default=str), capped=False)
    out.add("environment.json", dumps(environment, indent=2, default=str), capped=False)

    return out.finish(
        {
            "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
            "caps": {
                "record_bytes": RECORD_CAP,
                "ring_bytes": RING_CAP,
                "file_tail_bytes": file_cap,
                "error_blocks": ERROR_BLOCKS,
                "error_block_lines": ERROR_BLOCK_LINES,
                "total_bytes": total_cap,
            },
            "log_rules": (
                "File logging is active when CAPTURE_OUTPUT=yes or LOG_TYPES contains file with a valid LOG_FILE_PATH. "
                "Containers give the temporary UI its own tmp-ui.log, Linux shares the main UI files."
            ),
            "log_sources": source_report,
            "ring": {key: ring.get(key) for key in ("pid", "started", "bytes", "records_cut", "records_evicted")},
            "error_blocks": {"found": len(blocks), "kept": len(kept), "cut_at_line_cap": blocks_cut},
            "unavailable": unavailable,
            "anonymization": "Service domains, IP addresses, credentials and instance hostnames are anonymized; the license key and the database URI are never collected.",
        }
    )
