"""No Kubernetes-running action may assert the Docker app page without a k8s override.

On Kubernetes the ingress upstream is `nginxdemos/nginx-hello`
(`tests/misc/k8s/services.deployment.yml`), whose body never contains the `Hello World!` string
the Docker examples serve — its page carries `alt="NGINX Logo"` and a `Hello World` <title>
instead. An action that asserts `Hello World!` and runs on the Kubernetes arm therefore needs a
`Kubernetes:` override (`string:` or `xpath:`), the way `antibot.yml`'s six app-page assertions
carry one. `antibot.yml only_us_1` shipped without it in fe20de048 and kept the
`Kubernetes;antibot` job red after the action before it was fixed — this sweep fails on that
shape next to the diff that introduces it.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "tests" / "core"


def _runs_on_kubernetes(spec: dict) -> bool:
    integrations = spec.get("integrations", "all")
    if isinstance(integrations, str):
        return integrations == "all"
    return "Kubernetes" in integrations


def test_every_k8s_hello_world_assertion_carries_an_override():
    inspected = 0
    violations = []
    for path in sorted(CORE.glob("*.yml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict) or not _runs_on_kubernetes(spec):
            continue
        for name, action in (spec.get("actions") or {}).items():
            if not isinstance(action, dict) or "Hello World!" not in str(action.get("string", "")):
                continue
            inspected += 1
            override = action.get("Kubernetes")
            if not (isinstance(override, dict) and ("string" in override or "xpath" in override)):
                violations.append(f"{path.name}:{name}")
    assert inspected > 0, "the sweep matched nothing — the spec layout changed, fix the matcher"
    assert not violations, f"k8s-running actions asserting the Docker app page with no Kubernetes override: {violations}"
