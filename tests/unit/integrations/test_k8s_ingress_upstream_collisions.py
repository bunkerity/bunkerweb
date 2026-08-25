"""Two invariants a Kubernetes-running spec has to keep about its upstream.

On Kubernetes every spec gets an ingress it did not write: `generate.py` builds one rule from
the action's annotations (default host `www.example.com`, default path `/`) with `svc-app1` as
the backend, and the controller turns it into the service's numbered pair
(`REVERSE_PROXY_HOST_1` / `REVERSE_PROXY_URL_1`). That is fine until the spec also declares an
upstream of its own:

1. A spec that sets an **unsuffixed** `REVERSE_PROXY_HOST` renders it at `REVERSE_PROXY_URL`'s
   default `/`, so with the ingress still on `/` the same server block gets two `location /` and
   NGINX refuses the entire configuration:

       [emerg] duplicate location "/" in /etc/nginx/www.example.com/server-http/reverse-proxy.conf

   Nothing in the run says so — `tests/utils/config.yml:15` sets
   `DISABLE_CONFIGURATION_TESTING: "yes"` under `variables:`, i.e. for **every** integration in
   the suite, so the push goes out as `POST /reload?test=no` and the API answers
   `reload successful` 200 while the instance keeps the configuration it already had.
   `Kubernetes;mtls` failed on `Status code 400 not found in response, instead found 200` for
   exactly this reason: the pod never left its boot configuration, so mTLS was never enabled.

2. A `Kubernetes:` block must override the **same** key the base config sets. `custom-api` is a
   Docker compose name; inside a pod it resolves to the dnsmasq address `10.20.30.30`, which
   nothing there can reach, and the request hangs until the client gives up (`499`,
   `while connecting to upstream`). `cors.yml` overrode `BLACKLIST_IP_URLS` — a setting it never
   sets — instead of `REVERSE_PROXY_HOST`, and `Kubernetes;cors` timed out on
   `activated_allowed`.

Both sweeps fail on the shape, next to the diff that introduces it.

Ceiling of sweep 2: it matches `custom-api` by name, so it does not generalise to "any dotless
hostname a pod cannot resolve". Doing that would also flag `redis.yml`'s base
`REDIS_HOST: "redis"` — which its *actions* do override under their own `Kubernetes:` blocks, so
a spec-level rule would call it a violation without knowing whether the action that matters is
covered. Generalising needs the per-action merge that sweep 1 does, plus a decision on
`redis.yml` itself (ci-residue-3's scope).
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "tests" / "core"

# tests/models/action.py: every action carries this annotation unless the spec overrides it, and
# tests/generate.py turns it (plus REVERSE_PROXY_URL, default "/") into the ingress rule.
DEFAULT_ANNOTATIONS = {"bunkerweb.io/SERVER_NAME": "www.example.com"}

# tests/misc/docker/custom-api.yml. The k8s counterpart is svc-custom-api.misc.svc.cluster.local
# (tests/misc/k8s/custom-api.yml).
DOCKER_ONLY_UPSTREAM = "http://custom-api:"


def _runs_on_kubernetes(entry: dict, inherited) -> bool:
    integrations = entry.get("integrations", inherited)
    if isinstance(integrations, str):
        return integrations == "all"
    return "Kubernetes" in (integrations or [])


def _ingress_path(spec: dict, action: dict) -> str:
    # `tests/generate.py:195` is `test_annotations | action.annotations`, and the action side
    # wins -- so an action-level `annotations:` block moves the ingress for that action alone.
    # No spec uses one today; reading only the spec block would leave the guard bypassable
    # through the exact mechanism generate.py honours.
    annotations = DEFAULT_ANNOTATIONS | (spec.get("annotations") or {}) | (action.get("annotations") or {})
    return annotations.get("bunkerweb.io/REVERSE_PROXY_URL", annotations.get("REVERSE_PROXY_URL", "/"))


def _k8s_config(entry: dict) -> dict:
    return (entry.get("Kubernetes") or {}).get("config") or {}


def _specs():
    for path in sorted(CORE.glob("*.yml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(spec, dict) and _runs_on_kubernetes(spec, "all"):
            yield path, spec


def test_no_k8s_action_puts_its_own_upstream_on_the_ingress_path():
    inspected = 0
    violations = []
    for path, spec in _specs():
        base = (spec.get("config") or {}) | _k8s_config(spec)
        for name, action in (spec.get("actions") or {}).items():
            if not isinstance(action, dict) or not _runs_on_kubernetes(action, spec.get("integrations", "all")):
                continue
            config = base | (action.get("config") or {}) | _k8s_config(action)
            if not config.get("REVERSE_PROXY_HOST"):
                continue
            inspected += 1
            ingress_path = _ingress_path(spec, action)
            if config.get("REVERSE_PROXY_URL", "/") == ingress_path:
                violations.append(f"{path.name}:{name} (both on {ingress_path!r})")
    assert inspected > 0, "the sweep matched no unsuffixed REVERSE_PROXY_HOST — the spec layout changed, fix the matcher"
    assert not violations, f"unsuffixed reverse proxy sharing the ingress path — NGINX will refuse the config: {violations}"


def test_k8s_override_targets_the_same_key_as_the_docker_only_upstream():
    inspected = 0
    violations = []
    for path, spec in _specs():
        k8s = _k8s_config(spec)
        for key, value in (spec.get("config") or {}).items():
            if not isinstance(value, str) or DOCKER_ONLY_UPSTREAM not in value:
                continue
            inspected += 1
            if key not in k8s:
                violations.append(f"{path.name}:{key} (Kubernetes block overrides {sorted(k8s) or 'nothing'})")
    assert inspected > 0, "the sweep matched no custom-api upstream — the spec layout changed, fix the matcher"
    assert not violations, f"Docker-only upstream with no Kubernetes override for that key: {violations}"
