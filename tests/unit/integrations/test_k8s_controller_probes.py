"""The Kubernetes autoconf controller must outlive one scheduler apply-retry cycle.

``healthcheck-autoconf.sh`` reads ``/var/tmp/bunkerweb/autoconf.healthy``, and
``src/autoconf/main.py`` only writes that file after ``controller.wait()`` returns and the first
apply has run. ``wait()`` blocks on ``Config.have_to_wait()``, which is true while any of the
scheduler's change flags is set -- and those flags are cleared by the job that applies them
(``push-configs``), not by the scheduler on dispatch. When that job is late the scheduler is the
one that recovers, by re-dispatching after ``APPLY_RETRY_INTERVAL``.

So the controller's *liveness* budget is not a statement about the controller at all: it is a
deadline on somebody else's work. Sized below the scheduler's retry interval it kills a controller
that is behaving correctly, and a restart makes things strictly worse -- ``wait()`` starts over and
``initialDelaySeconds`` is owed again. Observed on run 32820557847 (k8s inject/errors/sessions):
liveness expired 350s after container start (observed kill at 355s), 18 seconds after the
scheduler's 300s re-dispatch, so it was SIGTERMed while its own retry was in flight and could not
report ready again before the 420s stack wait gave up. The kill also erased the first six minutes
of controller logs, since the failure dump runs ``kubectl logs`` without ``--previous``.

The rule below is therefore two full retry cycles: one for the apply that was late, one for the
scheduler's re-dispatch of it -- and, since a liveness probe that never fires would satisfy that
trivially, the pair is asserted too: readiness is where "has not applied yet" belongs (visible,
harmless), liveness is the backstop for a genuinely wedged event loop.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]

MANIFESTS = sorted((ROOT / "misc" / "integrations").glob("k8s.*.yml")) + [ROOT / "tests" / "k8s" / "bunkerweb.yml"]

CONTROLLER = "bunkerweb-controller"


def _apply_retry_interval() -> int:
    """The scheduler's re-dispatch interval, read from source so the two cannot drift apart."""
    source = (ROOT / "src" / "scheduler" / "main.py").read_text(encoding="utf-8")
    match = re.search(r'APPLY_RETRY_INTERVAL = int\(getenv\("APPLY_RETRY_INTERVAL", "(\d+)"\)', source)
    assert match, "APPLY_RETRY_INTERVAL is no longer defined the way this test reads it"
    return int(match.group(1))


APPLY_RETRY_INTERVAL = _apply_retry_interval()


def _controller_containers(path: Path):
    for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if not document or document.get("kind") != "Deployment":
            continue
        for container in document["spec"]["template"]["spec"]["containers"]:
            if container["name"] == CONTROLLER:
                yield container


def _budget(probe: dict) -> int:
    """Seconds from container start to the first kill/NotReady this probe can produce.

    `initialDelaySeconds + periodSeconds x (failureThreshold - 1)`, not `x failureThreshold`: the
    kubelet runs the probe for the first time AT `initialDelaySeconds`, so the Nth consecutive
    failure lands one period earlier than the naive product. For the controller's old 60/10/30 that
    is 350s, and run 32820557847 killed it at 355s -- the 5s of slack being probe execution plus
    the kubelet's own SIGTERM handling. Counting the extra period would make every rule below 10s
    laxer than it reads.
    """
    return probe.get("initialDelaySeconds", 0) + probe.get("periodSeconds", 10) * (probe.get("failureThreshold", 3) - 1)


def test_every_k8s_manifest_ships_a_controller():
    """A vacuous pass is the failure mode here: no controller found, nothing asserted."""
    for path in MANIFESTS:
        assert list(_controller_containers(path)), f"{path.relative_to(ROOT)}: no {CONTROLLER} container"


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: p.name)
def test_controller_declares_both_probes(path: Path):
    """Neither probe is optional, and skipping a missing one is how this file could lie.

    Liveness alone is what the eight shipped manifests had: a controller that has applied nothing
    still reads Ready, so the only externally visible symptom of "autoconf never got going" was the
    restart itself -- which the fix above deliberately postpones. Readiness alone would leave a
    genuinely wedged event loop (`Controller._settings_recheck_worker`, `_run_event_loop`) running
    forever with nothing to restart it. The pair is the design; assert the pair.
    """
    for container in _controller_containers(path):
        for kind in ("livenessProbe", "readinessProbe"):
            assert container.get(kind), f"{path.relative_to(ROOT)}: {CONTROLLER} has no {kind}"


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: p.name)
def test_controller_liveness_outlives_two_scheduler_apply_retries(path: Path):
    required = APPLY_RETRY_INTERVAL * 2
    for container in _controller_containers(path):
        probe = container.get("livenessProbe")
        assert probe, f"{path.relative_to(ROOT)}: {CONTROLLER} has no livenessProbe, so this budget is unbounded"
        budget = _budget(probe)
        assert budget >= required, (
            f"{path.relative_to(ROOT)}: {CONTROLLER} liveness kills at {budget}s, "
            f"before two {APPLY_RETRY_INTERVAL}s scheduler apply retries ({required}s) can complete"
        )


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: p.name)
def test_controller_liveness_is_never_tighter_than_its_readiness(path: Path):
    """Readiness is the probe that may fire while the controller waits; liveness must not beat it.

    Both run the same script, so a liveness budget at or below the readiness budget means the pod
    is restarted at the very moment it would have reported NotReady -- the caller watching
    readiness never gets to see the state it is waiting on.
    """
    for container in _controller_containers(path):
        liveness = container.get("livenessProbe")
        readiness = container.get("readinessProbe")
        assert liveness and readiness, f"{path.relative_to(ROOT)}: {CONTROLLER} does not declare both probes"
        assert _budget(liveness) > _budget(readiness), (
            f"{path.relative_to(ROOT)}: {CONTROLLER} liveness ({_budget(liveness)}s) does not outlast "
            f"its readiness ({_budget(readiness)}s), so a waiting controller is restarted instead of reported NotReady"
        )
