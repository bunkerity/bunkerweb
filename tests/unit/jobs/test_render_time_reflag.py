"""The two render-time jobs, executed rather than read.

`tests/unit/worker/test_job_delivery_contract.py` guards this whole class of defect, but it does it
by parsing source: it proves every core job that writes instance material also signals for delivery.
That is a marker. Changed-line coverage says so plainly -- of the lines these two rows changed, the
contract suite executes **zero**:

    download-crs-plugins.py    8 changed lines, 0 covered
    trusted-cert.py           14 changed lines, 0 covered

Both rows were accepted on the strength of a suite that never ran them. These tests run the two
regions with a stub `JOB`, because the specific failures here are ordering and short-circuit bugs
that a source-level assertion cannot see:

* `render_changed` must read the OLD fingerprint BEFORE `cache_file` overwrites it. Swap the two
  lines and the hash always matches, the flag never fires, and downloaded CRS plugins are shipped
  to every instance and never included -- which is exactly the bug the row fixed.
* `removed = drop_cache(...) or removed` must call `drop_cache` EVERY time. Written the other way
  round, `removed or drop_cache(...)` short-circuits once the first file is dropped and every
  later stale cert stays on disk, so mutual TLS never turns back off.

The region is lifted from the shipped file rather than retyped, so a rename breaks the test instead
of silently testing a copy that no longer matches what runs.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CRS_JOB = ROOT / "src" / "common" / "core" / "modsecurity" / "jobs" / "download-crs-plugins.py"
CERT_JOB = ROOT / "src" / "common" / "core" / "reverseproxy" / "jobs" / "trusted-cert.py"


class StubJob:
    """Records the call ORDER, which is the whole point: both defects are ordering bugs."""

    def __init__(self, present=(), hashes=None):
        self.present = set(present)
        self.hashes = hashes or {}
        self.calls = []

    def cache_hash(self, name, service_id=""):
        self.calls.append(("cache_hash", name))
        return self.hashes.get(name)

    def cache_file(self, name, content, service_id="", checksum=None):
        self.calls.append(("cache_file", name))
        self.hashes[name] = _fake_hash(content)
        return True, ""

    def del_cache(self, name, service_id=""):
        self.calls.append(("del_cache", service_id, name))
        self.present.discard((service_id, name))
        return True, ""

    @property
    def job_path(self):
        stub = self

        class _P:
            def __init__(self, parts=()):
                self.parts = parts

            def joinpath(self, *more):
                return _P(self.parts + more)

            def is_file(self):
                return (self.parts[0], self.parts[1]) in stub.present

        return _P()


def _fake_hash(content):
    return f"h:{len(content)}"


def lift(path: Path, start: str, end: str) -> str:
    body = path.read_text(encoding="utf-8")
    i = body.index(start)
    j = body.index(end, i)
    return body[i:j]


def test_the_crs_fingerprint_is_read_before_the_cache_is_overwritten():
    region = lift(CRS_JOB, "    plugins_json = dumps(", "    if not cached:")
    job = StubJob(hashes={"crs-plugins.json": "h:5"})
    env = {"JOB": job, "bytes_hash": _fake_hash, "dumps": lambda o, indent=None: "12345", "service_plugins": {}}

    exec(compile(region.replace("    ", "", 1).replace("\n    ", "\n"), "<crs>", "exec"), env)  # noqa: S102

    order = [name for name, *_ in job.calls]
    assert {"cache_hash", "cache_file"} <= set(order), f"region did not exercise both calls: {order}"
    assert order.index("cache_hash") < order.index("cache_file"), "the old fingerprint was read AFTER it was overwritten"
    assert env["render_changed"] is False, "identical content must not re-flag: the job would fire every day"


def test_changed_crs_content_sets_the_reflag():
    """The control: a fingerprint check that always returns False would pass the test above."""
    region = lift(CRS_JOB, "    plugins_json = dumps(", "    if not cached:")
    job = StubJob(hashes={"crs-plugins.json": "h:99"})
    env = {"JOB": job, "bytes_hash": _fake_hash, "dumps": lambda o, indent=None: "12345", "service_plugins": {}}

    exec(compile(region.replace("    ", "", 1).replace("\n    ", "\n"), "<crs>", "exec"), env)  # noqa: S102

    assert env["render_changed"] is True, "changed CRS content did not set the re-render flag"


def _run_removal(present, skipped, skipped_client):
    region = lift(CERT_JOB, "    def drop_cache(", "    if removed and status == 0:")
    job = StubJob(present=present)
    env = {
        "JOB": job,
        "skipped_servers": skipped,
        "skipped_client_servers": skipped_client,
        "CACHE_NAME": "trusted.pem",
        "CLIENT_CERT_CACHE_NAME": "client.pem",
        "CLIENT_KEY_CACHE_NAME": "client.key",
    }
    exec(compile(re.sub(r"^    ", "", region, flags=re.M), "<cert>", "exec"), env)  # noqa: S102
    return env["removed"], job


def test_every_stale_certificate_is_dropped_not_just_the_first():
    """`removed or drop_cache(...)` short-circuits after the first hit; the rest stay on disk and
    mutual TLS never turns back off. Two servers, both stale, is the smallest case that sees it."""
    removed, job = _run_removal(
        present=[("a.example.com", "trusted.pem"), ("b.example.com", "trusted.pem")],
        skipped=["a.example.com", "b.example.com"],
        skipped_client=[],
    )

    dropped = [service for name, service, _cache in job.calls if name == "del_cache"]
    assert removed is True
    assert dropped == ["a.example.com", "b.example.com"], f"only {dropped} were dropped"


def test_the_client_pair_is_dropped_together():
    removed, job = _run_removal(
        present=[("a.example.com", "client.pem"), ("a.example.com", "client.key")],
        skipped=[],
        skipped_client=["a.example.com"],
    )

    dropped = sorted(cache for name, _service, cache in job.calls if name == "del_cache")
    assert removed is True
    assert dropped == ["client.key", "client.pem"], "the cert and key must both go, or the templates still emit mTLS"


def test_nothing_stale_means_no_reflag():
    """The control. A removal path that always reports True would re-render the fleet every run."""
    removed, job = _run_removal(present=[], skipped=["a.example.com"], skipped_client=["a.example.com"])

    assert removed is False
    assert [name for name, *_ in job.calls].count("del_cache") == 3, "del_cache must still be attempted"
