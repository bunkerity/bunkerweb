"""Every Kubernetes workload the harness always deploys must appear in its failure dump.

`wait.sh` fails a Kubernetes job the moment one pod in the `bunkerweb` namespace stays not-ready,
and the only thing the run leaves behind is the dump `utils.sh` prints on failure. Run 32820557847
lost four Kubernetes jobs (inject, errors, sessions, upgrade) with a dump covering bunkerweb,
scheduler, controller and db only -- on `upgrade` all four of those were `Ready: True`, so the pod
that held the stack down was provably one the dump could not show. Since 1.7 the scheduler only
dispatches: push-configs, the job that ships the config and clears the change flags the
controller's readiness waits on, runs in the worker.

Both sides are derived, not hardcoded:

* the workloads come from the manifests `start.sh` copies into the kustomize root *outside* any
  `$type` gate -- `bunkerweb-ui.yml` is copied only for `type == ui`, so the UI is allowed to be
  dumped behind the matching gate;
* the coverage comes from the `kubectl` calls in `utils.sh` that sit outside any `$type` gate.

Ceiling: only manifests reached through `cp tests/k8s/...` are in scope -- a workload applied by
another route (`kubectl apply -f tests/misc/k8s/...`, say) is not covered here. And only `$type`
gating is modelled: a dump moved behind any OTHER conditional (`$FOLLOW`, `$integration`, ...)
still reads as covered.

A dump moved behind a type gate therefore reads as missing, which is the failure mode a plain
whole-file scrape cannot see: before this fix `bunkerweb-api` "passed" while it was gated behind
`elif [ "$type" == "api" ]` and never ran for the `core` jobs that needed it.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
K8S_DIR = ROOT / "tests" / "k8s"
UTILS = ROOT / "tests" / "scripts" / "utils.sh"
START = ROOT / "tests" / "scripts" / "start.sh"

# The namespace the always-applied manifests declare; wait.sh judges that namespace and no other.
NAMESPACE = "bunkerweb"

_IF = re.compile(r"^\s*if\s")
_ELIF = re.compile(r"^\s*elif\s")
_FI = re.compile(r"^\s*fi\s*$")
_TYPE_GATE = re.compile(r'^\s*(?:el)?if \[+ "\$type"')


def _lines_outside_type_gates(path: Path):
    """The lines of a shell script that run whatever `$type` is.

    A depth tracker rather than a slice: a dump appended *after* the `type == ui` block is still
    unconditional, and a slice ending at the first gate would wrongly call it missing. `else`
    keeps its `if`'s verdict -- the other branch of a type gate is just as conditional.
    """
    gates, kept = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if _FI.match(line):
            assert (
                gates
            ), f"cannot parse {path.name}: `fi` with no open `if` at {line!r} (one-liner `if ...; fi`, or a heredoc containing `fi`?) -- the scrape below cannot be trusted"
            gates.pop()
            continue
        if _ELIF.match(line):
            assert gates, f"`elif` outside any `if` in {path.name}: {line!r}"
            gates[-1] = gates[-1] or bool(_TYPE_GATE.match(line))
            continue
        if _IF.match(line):
            gates.append(bool(_TYPE_GATE.match(line)))
            continue
        if not any(gates):
            kept.append(line)
    assert (
        not gates
    ), f"cannot parse {path.name}: unmatched `if` (one-liner `if ...; fi`, trailing content after `fi`, or a heredoc containing `if`?) -- the scrape below cannot be trusted"
    return kept


def _always_applied_manifests():
    """The tests/k8s manifests start.sh applies for every type."""
    names = set()
    for line in _lines_outside_type_gates(START):
        match = re.search(r"cp tests/k8s/(\S+\.ya?ml)\b", line)
        if match:
            names.add(match.group(1))
    return names


def _always_deployed_app_labels():
    labels = set()
    for name in sorted(_always_applied_manifests()):
        manifest = K8S_DIR / name
        assert manifest.is_file(), f"start.sh copies {manifest} but it does not exist"
        labels.update(re.findall(r"^\s*app:\s*(\S+)\s*$", manifest.read_text(encoding="utf-8"), re.MULTILINE))
    return labels


def _dumped(verb: str):
    """Labels dumped with `verb` from the bunkerweb namespace, outside any type gate."""
    pattern = re.compile(rf"kubectl {verb} -n {re.escape(NAMESPACE)}(?=\s) -l app=(\S+)")
    return {match.group(1) for line in _lines_outside_type_gates(UTILS) for match in pattern.finditer(line)}


def test_start_sh_type_gate_parse_is_sane():
    # Guards the guard on both sides: the always-applied set must contain what every job gets and
    # must exclude what only `type == ui` gets. A parser that returned everything, or nothing,
    # would make the coverage tests below vacuous rather than red.
    manifests = _always_applied_manifests()
    assert {"bunkerweb.yml", "bunkerweb-api.yml"} <= manifests, manifests
    assert "bunkerweb-ui.yml" not in manifests, manifests


def test_manifest_app_labels_are_bunkerweb_prefixed():
    # The dump greps by `app=` label; a workload labelled anything else would still deploy, still
    # be judged by wait.sh, and quietly need its own dump line. Assert the assumption rather than
    # filtering on it -- filtering is how such a workload would disappear from this file's scope.
    labels = _always_deployed_app_labels()
    assert labels, "no app labels scraped from the always-applied manifests"
    odd = sorted(label for label in labels if not label.startswith("bunkerweb"))
    assert not odd, f"app label(s) outside the bunkerweb* namespace convention: {', '.join(odd)}"


def test_every_always_deployed_workload_has_a_log_dump():
    missing = sorted(_always_deployed_app_labels() - _dumped("logs"))
    assert not missing, f"Kubernetes failure dump has no type-unconditional `kubectl logs` for: {', '.join(missing)}"


def test_every_always_deployed_workload_has_a_pod_description():
    missing = sorted(_always_deployed_app_labels() - _dumped("describe pods"))
    assert not missing, f"Kubernetes failure dump has no type-unconditional `kubectl describe pods` for: {', '.join(missing)}"
