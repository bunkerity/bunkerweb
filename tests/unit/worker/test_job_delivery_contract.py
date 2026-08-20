"""The job -> instance delivery contract: exit 1, or your output never leaves the worker.

A core plugin job that writes into ``/var/cache/bunkerweb`` has produced nothing an instance can
use until something *pushes* that tree. There are exactly two pushers, and both are triggered by
the job's exit code:

  * ``_request_reload_debounced`` (``src/worker/tasks.py``), called from ``if ret == 1 and apis:``
  * ``push-configs``, dispatched by the scheduler on ``RUN_JOBS_ONCE`` or a config change

Nothing else. ``upsert_job_cache`` raises no metadata flag -- there is no ``job_cache_changed`` to
go with ``config_changed`` and friends -- and ``plugin.json``'s ``reload`` key is declarative only:
it is validated and persisted, never consulted to decide a push. **The exit code is the whole
trigger.** A job that caches a file and exits 0 has no convergence path of its own.

That is not automatically a defect, because both pushers ship the *whole* cache tree: a job that
exits 0 piggybacks on any sibling that exits 1. It becomes a defect when the piggyback cannot
happen. Three conditions together:

  1. the plugin's cache directory is genuinely read on an instance,
  2. no job of that plugin can exit 1, and
  3. the job runs ``every: "once"`` -- so it fires once, at first start, and never again.

``crowdsec-conf`` held all three. Measured on 2026-08-20: ``push-configs`` shipped ``/cache`` at
T, ``crowdsec-conf`` wrote ``crowdsec/crowdsec.conf`` at T+3s and exited 0, and the file was still
on the worker alone 63 seconds later when the stack came down. ``crowdsec:init()`` reads that path
once, so ``Allow()`` threw on every request and the WAF served 200 where the spec wanted 403 --
while the job reported success in the logs, in ``bw_jobs`` and in the UI.

**On the exit-1 detector.** A ``status = 1`` regex is not good enough: ``geoip`` reaches it through
``geoip_utils.run()`` and ``self-signed`` through ``return True, 1``, and a naive pattern produced
three false positives that had to be retracted. This module walks the AST of every ``.py`` under
the plugin's ``jobs/`` directory and counts a literal 1 only where it can become an exit code --
an argument of an ``*exit`` call, a ``return`` value, or an assignment to a name that is later
passed to ``*exit``. It is deliberately **generous**: anything it cannot prove absent counts as
"can signal". So its errors are missed defects, never false alarms. It is per-plugin, not per-job,
which matches how the piggyback actually works within a plugin's own cache directory.
"""

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"

# Where an instance reads its cache from. ``src/bw/lua`` matters on its own: ``geoip``'s consumer
# is ``bw/lua/bunkerweb/mmdb.lua``, not anything under the plugin's own directory. Conf templates
# count too -- ``reverseproxy`` only *references* its trusted-CA path, so the instance still needs
# the file on disk.
CONSUMER_ROOTS = (ROOT / "src" / "bw" / "lua", CORE)
CONSUMER_SUFFIXES = (".lua", ".conf", ".modsec")

CACHE_ROOT = "/var/cache/bunkerweb"


def _is_literal_one(node: ast.AST) -> bool:
    """True if a literal integer 1 appears anywhere in this subtree.

    ``isinstance(value, bool)`` is not redundant: ``True == 1`` in Python, and ``return True, 1``
    would otherwise match on the wrong element and hide whether the real 1 is there.
    """
    return any(isinstance(n, ast.Constant) and not isinstance(n.value, bool) and n.value == 1 for n in ast.walk(node))


def _is_exit_call(node: ast.Call) -> bool:
    """``sys_exit(...)``, ``exit(...)``, ``sys.exit(...)`` -- however the job spelled the import."""
    func = node.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
    return name.endswith("exit")


def _assign_targets(node) -> set:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return {t.id for t in targets if isinstance(t, ast.Name)}


def exit_one_sites(source_file: Path) -> list:
    """Every place in one file where a literal 1 can become the process exit code.

    Returns ``["<name>:<line> <kind>", ...]`` -- evidence, so a failure says *why* rather than just
    "false".
    """
    try:
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        # Unparseable is not provably free of an exit-1 path, and this detector only ever claims
        # absence. Report a site so the caller stays on the safe side.
        return [f"{source_file.name}:0 unparseable"]

    # Names whose value reaches an exit call: `sys_exit(status)` makes `status` an exit code, so a
    # later `status = 1` counts, while an unrelated `timeout = 1` does not.
    exit_code_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_exit_call(node):
            exit_code_names.update(arg.id for arg in node.args if isinstance(arg, ast.Name))

    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_exit_call(node):
            if any(_is_literal_one(arg) for arg in node.args):
                sites.append(f"{source_file.name}:{node.lineno} exit-call")
        elif isinstance(node, ast.Return) and node.value is not None and _is_literal_one(node.value):
            sites.append(f"{source_file.name}:{node.lineno} return")
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)) and node.value is not None:
            if _is_literal_one(node.value) and _assign_targets(node) & exit_code_names:
                sites.append(f"{source_file.name}:{node.lineno} status-assign")
    return sorted(sites)


def plugin_exit_one_sites(plugin_dir: Path) -> list:
    """Exit-1 evidence across a plugin's whole ``jobs/`` directory, helper modules included.

    Helpers are the point: ``geoip-country.py`` only does ``status = run(...)``, and the ``return 1``
    lives in ``geoip_utils.py`` next to it.
    """
    jobs_dir = plugin_dir / "jobs"
    if not jobs_dir.is_dir():
        return []
    sites = []
    for source_file in sorted(jobs_dir.rglob("*.py")):
        sites += exit_one_sites(source_file)
    return sites


def instance_reads_cache_of(plugin_id: str, consumer_roots=CONSUMER_ROOTS) -> list:
    """Files on the instance side that name this plugin's cache directory."""
    needle = f"{CACHE_ROOT}/{plugin_id}"
    readers = []
    for root in consumer_roots:
        if not root.is_dir():
            continue
        for candidate in sorted(root.rglob("*")):
            if not candidate.is_file() or candidate.suffix not in CONSUMER_SUFFIXES:
                continue
            if needle in candidate.read_text(encoding="utf-8", errors="ignore"):
                # Repo-relative when it is in the repo; the fixtures below plant readers under
                # tmp_path, which is not, and `relative_to` raises rather than falling back.
                readers.append(candidate.relative_to(ROOT).as_posix() if candidate.is_relative_to(ROOT) else candidate.as_posix())
    return readers


def undeliverable_jobs(core_dir=CORE, consumer_roots=CONSUMER_ROOTS) -> list:
    """Jobs holding all three conditions. Each entry carries the evidence for the two it satisfies."""
    broken = []
    for manifest in sorted(core_dir.glob("*/plugin.json")):
        plugin_dir = manifest.parent
        plugin_id = plugin_dir.name
        jobs = json.loads(manifest.read_text(encoding="utf-8")).get("jobs") or []
        if not jobs:
            continue

        if plugin_exit_one_sites(plugin_dir):
            continue  # (2) fails: something in this plugin can signal, so the tree gets pushed

        readers = instance_reads_cache_of(plugin_id, consumer_roots)
        if not readers:
            continue  # (1) fails: nothing on an instance reads this plugin's cache

        for job in jobs:
            if job.get("every") == "once":  # (3): one shot, no later run to piggyback on
                broken.append((plugin_id, job.get("name"), readers))
    return broken


def test_no_core_job_writes_instance_material_it_can_never_deliver():
    """The contract itself, over the real tree.

    A failure here means: this job caches a file an instance reads, nothing in its plugin can exit
    1 to push it, and it runs once so it will not get another chance. Fix the job's exit code --
    ``status = 1`` on the branch that wrote the file -- not this test.
    """
    broken = undeliverable_jobs()
    assert broken == [], "job(s) whose cached output can never reach an instance: " + "; ".join(
        f"{plugin}/{job} (read by {', '.join(readers)})" for plugin, job, readers in broken
    )


class TestDetectorBites:
    """Anti-vacuity. A guard that flags nothing because its detector matches nothing is worse than
    no guard, so each of the three conditions is shown to fail a plugin that violates it, and the
    real crowdsec job is shown to flip red the moment its exit-1 path goes away."""

    @staticmethod
    def _plant(tmp_path: Path, plugin_id: str, source: str, *, every: str = "once", helper: str = "") -> Path:
        """Build a one-plugin core tree plus the instance-side reader that makes it matter."""
        core = tmp_path / "core"
        jobs = core / plugin_id / "jobs"
        jobs.mkdir(parents=True)
        (core / plugin_id / "plugin.json").write_text(
            json.dumps({"id": plugin_id, "jobs": [{"name": f"{plugin_id}-conf", "file": "job.py", "every": every}]}),
            encoding="utf-8",
        )
        (jobs / "job.py").write_text(source, encoding="utf-8")
        if helper:
            (jobs / "helper.py").write_text(helper, encoding="utf-8")

        lua = tmp_path / "lua"
        lua.mkdir()
        (lua / f"{plugin_id}.lua").write_text(f'local f = open("{CACHE_ROOT}/{plugin_id}/thing.conf", "r")\n', encoding="utf-8")
        return core

    # A job in the shape crowdsec had: caches a file, exits 0 either way.
    NEVER_SIGNALS = "from sys import exit as sys_exit\nstatus = 0\nJOB.cache_file('thing.conf', content)\nsys_exit(status)\n"

    def test_a_once_job_that_never_signals_is_flagged(self, tmp_path):
        core = self._plant(tmp_path, "acme", self.NEVER_SIGNALS)
        assert [(p, j) for p, j, _ in undeliverable_jobs(core, (tmp_path / "lua",))] == [("acme", "acme-conf")]

    def test_a_bare_literal_one_elsewhere_does_not_count_as_signalling(self, tmp_path):
        """The false-positive class that forced three retractions: a 1 that is not an exit code."""
        source = "from sys import exit as sys_exit\nstatus = 0\ntimeout = 1\nretries = 1 + 1\nsys_exit(status)\n"
        core = self._plant(tmp_path, "acme", source)
        assert [(p, j) for p, j, _ in undeliverable_jobs(core, (tmp_path / "lua",))] == [("acme", "acme-conf")]

    def test_condition_two_bites_on_a_direct_exit(self, tmp_path):
        source = "from sys import exit as sys_exit\nstatus = 0\nif changed:\n    status = 1\nsys_exit(status)\n"
        core = self._plant(tmp_path, "acme", source)
        assert undeliverable_jobs(core, (tmp_path / "lua",)) == []

    def test_condition_two_bites_through_a_helper_module(self, tmp_path):
        """The geoip shape: the job only does ``status = run(...)`` and the 1 lives next door."""
        core = self._plant(tmp_path, "acme", self.NEVER_SIGNALS.replace("status = 0", "status = run()"), helper="def run():\n    return 1\n")
        assert undeliverable_jobs(core, (tmp_path / "lua",)) == []

    def test_condition_two_bites_on_a_tuple_return(self, tmp_path):
        """The self-signed shape: ``return True, 1``, where ``True == 1`` must not be what matches."""
        core = self._plant(tmp_path, "acme", self.NEVER_SIGNALS, helper="def generate():\n    return True, 1\n")
        assert undeliverable_jobs(core, (tmp_path / "lua",)) == []

    def test_condition_three_bites_on_a_scheduled_job(self, tmp_path):
        """Hourly is not the same exposure: the next run gets another chance to push."""
        core = self._plant(tmp_path, "acme", self.NEVER_SIGNALS, every="hour")
        assert undeliverable_jobs(core, (tmp_path / "lua",)) == []

    def test_condition_one_bites_when_no_instance_reads_the_cache(self, tmp_path):
        core = self._plant(tmp_path, "acme", self.NEVER_SIGNALS)
        empty = tmp_path / "no-readers"
        empty.mkdir()
        assert undeliverable_jobs(core, (empty,)) == []

    def test_the_real_crowdsec_job_goes_red_without_its_exit_one(self, tmp_path):
        """Mutation on a copy of the shipped job -- ``src/`` is never touched.

        Pins the fix in place: revert ``status = 1`` and this test, not just the contract test,
        says so.
        """
        live = CORE / "crowdsec" / "jobs" / "crowdsec-conf.py"
        source = live.read_text(encoding="utf-8")
        assert exit_one_sites(live), f"{live.name} has no exit-1 path to remove -- the contract is already broken"

        mutated = source.replace("status = 1", "status = 0")
        assert mutated != source, "mutation did not apply; the fix no longer spells its exit code `status = 1`"

        core = self._plant(tmp_path, "crowdsec", mutated)
        assert [(p, j) for p, j, _ in undeliverable_jobs(core, (tmp_path / "lua",))] == [("crowdsec", "crowdsec-conf")]

        # ... and the unmutated copy of the same file is clean, so the flag came from the mutation
        # and not from anything the copying did.
        clean = self._plant(tmp_path / "clean", "crowdsec", source)
        assert undeliverable_jobs(clean, (tmp_path / "clean" / "lua",)) == []


# --------------------------------------------------------------------------------------
# Second predicate: exit 1 means "changed", so an error path must never use it
# --------------------------------------------------------------------------------------
# The contract is one-directional and the worker cannot tell the two meanings apart. A job that
# exits 1 because it *failed* gets the treatment meant for a job that succeeded and changed
# something: `_request_reload_debounced` pushes /var/cache/bunkerweb to every instance and issues
# `POST /reload` across the fleet. And `tasks.py` counts `success = ret in (0, 1)`, so the failed
# run is written to `bw_jobs` as a success -- invisible in the job history and in the UI.
#
# So a failed database cleanup or a failed GitHub fetch reloads nginx everywhere and reports fine.
#
# **Telling an error path from a success path soundly is the whole difficulty.** 1 is legitimate on
# the success-with-change branch, and most jobs use it that way. Neither "returns 1 somewhere" nor
# "returns 1 near a LOGGER.error" works -- measured on this tree they flag 43 and 26 sites, almost
# all of them correct uses. What is provable is a narrower shape: a block that does **nothing but
# report a failure and leave**. Every statement in it is a logging call, an assignment of literal 1
# to a name that becomes the exit code, or the exit itself; at least one of those logging calls is
# `error`/`critical`/`exception`. A branch that logs a failure and then does real work -- retries,
# cleanup, bookkeeping -- is not matched, and that is a miss this predicate accepts.
#
# Same asymmetry as the first predicate: generous about what it lets through, never about what it
# accuses. Its errors are missed error paths, not false alarms.
#
# **Scope: files a `plugin.json` actually declares as jobs.** Only those exit codes reach
# `tasks.py`. `certbot-auth.py` and `certbot-cleanup.py` set `status = 1` on a failed API call and
# look identical to the sites below, but letsencrypt declares only `certbot-new.py` and
# `certbot-renew.py` -- the hooks' exit codes go to certbot, not to the worker. Flagging them would
# be the false alarm this guard exists to avoid. Helper modules are out for the same reason: a
# helper's `return 1` only becomes an exit code if its caller passes it on, and that is a call graph.
NEUTRAL_LOG_METHODS = {"debug", "info", "warning", "warn", "error", "critical", "exception"}
FAILURE_LOG_METHODS = {"error", "critical", "exception"}


def _is_log_call(stmt, methods) -> bool:
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute) and stmt.value.func.attr in methods


def _statement_blocks(tree):
    """Every statement list in the tree -- ``body``, ``orelse``, ``finalbody`` and each handler."""
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and block and all(isinstance(s, ast.stmt) for s in block):
                yield block
        for handler in getattr(node, "handlers", None) or []:
            yield handler.body


def error_path_exit_one_sites(job_file: Path) -> list:
    """Sites where a pure failure branch of a declared job hands the worker a 1."""
    try:
        tree = ast.parse(job_file.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    exit_code_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_exit_call(node):
            exit_code_names.update(arg.id for arg in node.args if isinstance(arg, ast.Name))

    found = {}
    for block in _statement_blocks(tree):
        sites, pure = [], True
        for stmt in block:
            if _is_log_call(stmt, NEUTRAL_LOG_METHODS):
                continue
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and _is_exit_call(stmt.value):
                if any(_is_literal_one(arg) for arg in stmt.value.args):
                    sites.append((stmt.lineno, "exit(1)"))
                elif not all(isinstance(arg, ast.Name) and arg.id in exit_code_names for arg in stmt.value.args):
                    pure = False  # exits with something else entirely -- not this shape
                continue
            if isinstance(stmt, ast.Return) and stmt.value is not None:
                if isinstance(stmt.value, ast.Constant) and _is_literal_one(stmt.value):
                    sites.append((stmt.lineno, "return 1"))
                else:
                    pure = False
                continue
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and getattr(stmt, "value", None) is not None:
                value = stmt.value
                if isinstance(value, ast.Constant) and _is_literal_one(value) and _assign_targets(stmt) & exit_code_names:
                    sites.append((stmt.lineno, "status = 1"))
                    continue
                pure = False
                continue
            pure = False  # anything else means the branch does real work, so this is not the shape

        if pure and sites and any(_is_log_call(s, FAILURE_LOG_METHODS) for s in block):
            for lineno, kind in sites:
                found.setdefault(lineno, f"{job_file.name}:{lineno} {kind}")
    return [found[k] for k in sorted(found)]


def declared_job_files(core_dir=CORE) -> list:
    """The files a ``plugin.json`` names as jobs -- the only exit codes the worker ever sees."""
    files = []
    for manifest in sorted(core_dir.glob("*/plugin.json")):
        for job in json.loads(manifest.read_text(encoding="utf-8")).get("jobs") or []:
            candidate = manifest.parent / "jobs" / job.get("file", "")
            if candidate.is_file():
                files.append(candidate)
    return files


def error_paths_using_the_reload_code(core_dir=CORE) -> list:
    sites = []
    for job_file in declared_job_files(core_dir):
        sites += [f"{job_file.parent.parent.name}/{site}" for site in error_path_exit_one_sites(job_file)]
    return sites


def test_no_job_error_path_uses_the_reload_exit_code():
    """A job that failed must not exit 1 -- that is the code for "changed, push and reload".

    Currently red, deliberately and with the manager's sign-off, on the sites listed in the failure
    message. Each one reloads nginx across the fleet because a cleanup or a fetch failed, and each
    is recorded as a successful run. The fix is per-site: use 2, which the worker reads as a failure.
    """
    sites = error_paths_using_the_reload_code()
    assert sites == [], "error path(s) exiting 1, which the worker reads as 'changed, reload the fleet':\n  " + "\n  ".join(sites)


class TestErrorPathDetectorBites:
    """The same anti-vacuity discipline as the first predicate: show it matching the shape it means
    and, more importantly, *not* matching the legitimate use of 1 that surrounds it everywhere."""

    @staticmethod
    def _plant(tmp_path: Path, body: str, *, name: str = "job.py") -> Path:
        core = tmp_path / "core"
        jobs = core / "acme" / "jobs"
        jobs.mkdir(parents=True)
        (core / "acme" / "plugin.json").write_text(json.dumps({"id": "acme", "jobs": [{"name": "acme-job", "file": name, "every": "day"}]}), encoding="utf-8")
        (jobs / name).write_text(body, encoding="utf-8")
        return core

    def test_a_pure_failure_branch_exiting_one_is_flagged(self, tmp_path):
        body = "from sys import exit as sys_exit\nif not ok:\n    LOGGER.error(msg)\n    sys_exit(1)\nsys_exit(0)\n"
        assert error_paths_using_the_reload_code(self._plant(tmp_path, body)) == ["acme/job.py:4 exit(1)"]

    def test_the_status_assign_shape_is_flagged_too(self, tmp_path):
        """``update-check`` sets the code first and logs after, so order must not matter."""
        body = "from sys import exit as sys_exit\nstatus = 0\nif not release:\n    status = 1\n    LOGGER.error('failed to fetch')\n    sys_exit(status)\nsys_exit(status)\n"
        assert error_paths_using_the_reload_code(self._plant(tmp_path, body)) == ["acme/job.py:4 status = 1"]

    def test_an_error_path_exiting_two_is_not_flagged(self, tmp_path):
        """2 is the correct code. The guard must not object to a job that already gets this right."""
        body = "from sys import exit as sys_exit\nif not ok:\n    LOGGER.error(msg)\n    sys_exit(2)\nsys_exit(0)\n"
        assert error_paths_using_the_reload_code(self._plant(tmp_path, body)) == []

    def test_a_success_branch_returning_one_is_not_flagged(self, tmp_path):
        """The legitimate use, and the one a looser predicate destroys: 1 means "I changed something"."""
        body = "from sys import exit as sys_exit\nstatus = 0\nif changed:\n    JOB.cache_file('x', data)\n    status = 1\nsys_exit(status)\n"
        assert error_paths_using_the_reload_code(self._plant(tmp_path, body)) == []

    def test_a_failure_branch_that_does_real_work_is_not_flagged(self, tmp_path):
        """The accepted miss, pinned so it stays a decision rather than becoming a surprise."""
        body = "from sys import exit as sys_exit\nif not ok:\n    LOGGER.error(msg)\n    cleanup()\n    sys_exit(1)\nsys_exit(0)\n"
        assert error_paths_using_the_reload_code(self._plant(tmp_path, body)) == []

    def test_an_undeclared_helper_is_not_scanned(self, tmp_path):
        """A hook or helper next to the jobs hands its exit code to whoever ran it, not the worker.

        This is why `certbot-auth.py` and `certbot-cleanup.py` are absent from the real finding.
        """
        core = self._plant(tmp_path, "from sys import exit as sys_exit\nsys_exit(0)\n")
        helper = core / "acme" / "jobs" / "hook.py"
        helper.write_text("from sys import exit as sys_exit\nif not sent:\n    LOGGER.error(err)\n    sys_exit(1)\n", encoding="utf-8")
        assert error_paths_using_the_reload_code(core) == []

    def test_the_predicate_finds_something_in_the_real_tree(self):
        """Anti-vacuity against the live tree: the detector must match real code, not just fixtures.

        Drop this expectation only when the last site is fixed and
        ``test_no_job_error_path_uses_the_reload_exit_code`` goes green -- at which point the two
        assertions contradict each other and this one is the one to delete.
        """
        assert declared_job_files(), "no declared jobs found -- the manifest walker is broken"


def test_every_core_job_is_classified():
    """Coverage, so a new plugin cannot slip past by being invisible to the walker.

    The audit of 2026-08-20 counted 35 jobs across ``src/common/core``. If this number moves, the
    contract test above needs re-reading against the new job, not a bumped constant.
    """
    total = sum(len(json.loads(m.read_text(encoding="utf-8")).get("jobs") or []) for m in CORE.glob("*/plugin.json"))
    assert total >= 35, f"only {total} core jobs found -- the plugin walker is not seeing the tree"


if __name__ == "__main__":  # pragma: no cover - convenience for a quick manual look
    for plugin, job, readers in undeliverable_jobs():
        print(f"UNDELIVERABLE  {plugin}/{job}  read by {', '.join(readers)}")
    raise SystemExit(pytest.main([__file__, "-q"]))
