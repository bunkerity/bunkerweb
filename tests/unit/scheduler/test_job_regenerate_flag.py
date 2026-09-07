"""The ``regenerate`` job flag, scheduler side.

``regenerate`` tells the Worker that this job's output is read at RENDER time — a template
that inlines a downloaded list, or probes a cached certificate with ``is_file()`` — so a
cache push alone leaves the instances reloading a configuration that predates the change.
1.6 hardcoded an allowlist of two core jobs in the Scheduler; 1.7 reads the flag from each
plugin's own ``plugin.json``, which is what makes it reachable for external and PRO plugins.

Two things are pinned here:
  * the flag survives validation and reaches the dispatch payload (it is dropped nowhere);
  * the flag and the hand-rolled ``checked_changes`` call are never both used by one job.

The "every render-time consumer asks for a re-render" guard is NOT duplicated here: it already
exists, and better, as ``test_every_render_time_consumer_has_a_job_that_asks_for_a_re_render`` in
``tests/unit/worker/test_job_delivery_contract.py`` — that one attributes a template to the plugin
that OWNS the cache path it reads (``grpc`` reads ``reverseproxy``'s) and requires a real
render-time probe rather than a bare path mention. It now recognises the manifest flag as a second
way of asking.
"""

import json
import logging
from pathlib import Path

import pytest

from JobScheduler import JobScheduler  # type: ignore  (src/scheduler on path; needs `schedule`)

LOGGER = logging.getLogger("sched-regen-test")
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.CRITICAL)

CORE = Path(__file__).resolve().parents[3] / "src" / "common" / "core"


@pytest.fixture
def js():
    return JobScheduler(LOGGER)


def _validate(js, jobs):
    return js._JobScheduler__validate_jobs(jobs, "plug", "/path/plugin.json")


def _job(**over):
    job = {"name": "j", "file": "j.py", "every": "hour", "reload": True}
    job.update(over)
    return job


class TestValidation:
    def test_regenerate_true_survives_validation(self, js):
        out = _validate(js, [_job(regenerate=True)])
        assert len(out) == 1 and out[0]["regenerate"] is True

    def test_regenerate_absent_is_valid(self, js):
        assert len(_validate(js, [_job()])) == 1

    def test_non_bool_regenerate_skipped(self, js):
        # Same treatment `reload` gets: a string is not a silently-truthy flag.
        assert _validate(js, [_job(regenerate="yes")]) == []


class TestDispatchPayload:
    def test_flag_reaches_the_payload(self, js):
        item = js._build_dispatch_item(_job(path="/p", regenerate=True), "pl")
        assert item["regenerate"] is True

    def test_default_is_false(self, js):
        assert js._build_dispatch_item(_job(path="/p"), "pl")["regenerate"] is False


class TestShippedManifests:
    """The core plugins whose templates read the job cache and whose job wants it on every exit 1.

    ``modsecurity`` is deliberately absent. Its job re-renders on a narrower condition than the
    flag can express -- ``download-crs-plugins.py`` only wants a render when the CRS *plugin set*
    changed (``if render_changed and status == 1``), while ``status`` is set to 1 unconditionally
    on that path -- so it keeps calling ``checked_changes`` itself. Declaring the flag as well
    would re-render and reload the whole fleet daily for an unchanged plugin set.
    """

    EXPECTED = {
        "realip": "realip-download",
        "reverseproxy": "trusted-cert",
    }

    @pytest.mark.parametrize("plugin_id,job_name", sorted(EXPECTED.items()))
    def test_declared(self, plugin_id, job_name):
        jobs = json.loads((CORE / plugin_id / "plugin.json").read_text(encoding="utf-8"))["jobs"]
        job = next(j for j in jobs if j["name"] == job_name)
        assert job.get("regenerate") is True, f"{plugin_id}/{job_name} must declare regenerate"

    def test_no_other_core_job_declares_it(self):
        """Not a style rule: the flag costs a full render plus one re-dispatch of the plugin."""
        extra = []
        for manifest in sorted(CORE.glob("*/plugin.json")):
            plugin_id = manifest.parent.name
            for job in json.loads(manifest.read_text(encoding="utf-8")).get("jobs", []):
                if job.get("regenerate") and self.EXPECTED.get(plugin_id) != job["name"]:
                    extra.append(f"{plugin_id}/{job['name']}")
        assert extra == []

    def test_a_job_that_flags_by_hand_does_not_also_declare_the_flag(self):
        """Both at once is a double re-render. The hand-rolled call is the escape hatch for a job
        whose condition is narrower than "exited 1"; a job using it must not declare the flag."""
        both = []
        for manifest in sorted(CORE.glob("*/plugin.json")):
            plugin_id = manifest.parent.name
            declared = {j["name"] for j in json.loads(manifest.read_text(encoding="utf-8")).get("jobs", []) if j.get("regenerate")}
            if not declared:
                continue
            for job_file in sorted((manifest.parent / "jobs").glob("*.py")) if (manifest.parent / "jobs").is_dir() else []:
                if job_file.stem in {n.replace("-", "_") for n in declared} or job_file.stem in declared:
                    # Comment lines dropped: both of these files carry a comment saying the
                    # hand-rolled call was REMOVED in favour of the flag, and matching that would
                    # make this test assert the opposite of what it is for.
                    code = "\n".join(line for line in job_file.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#"))
                    if "checked_changes(" in code:
                        both.append(f"{plugin_id}/{job_file.name}")
        assert both == [], "these jobs declare `regenerate` AND flag by hand: " + ", ".join(both)
