"""A per-integration override in a spec must only carry keys the action model knows.

`parse_action` (`tests/utils/action.py`) folds `Docker:` / `Linux:` / `Autoconf:` /
`Kubernetes:` / `All-in-one:` into the action, then hands the result to a pydantic model that
**ignores** everything it does not declare. Two mistakes therefore change what an arm runs
without failing anything:

* a BunkerWeb setting written directly under the arm instead of under its `config:` -- it is
  dropped, and the arm silently keeps the base config's value;
* `config:` left EMPTY above those settings, which makes it `None` -- and a `None` override
  means "remove this key", so the merge deletes the action's WHOLE config block for that arm.

Both shipped together in `antibot.yml`'s `capjs` action: on Linux the four PHP keys sat beside
`config:` rather than inside it, so the arm lost `USE_ANTIBOT=capjs`, every `ANTIBOT_CAPJS_*`
setting and the local PHP upstream at once. The page under test became the spec-level captcha
challenge, `//h1[contains(text(),'Hello World!')]` was never going to be there, and the only
signal was a Selenium timeout on the app page. The sibling action `ignore_us` carries the same
four keys correctly indented, which is what makes this a typo rather than a design.

Uppercase is the discriminator on purpose: no field of any action model is uppercase, and every
BunkerWeb setting is. Type-specific model fields (`string`, `status`, `xpath`, `port`, `db`,
`response_headers`, ...) are lowercase and legitimately appear in overrides, so they pass.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC_DIRS = ("core", "ui", "api")
ARMS = ("Docker", "Linux", "Autoconf", "Swarm", "Kubernetes", "All-in-one")


def _overrides():
    """Yield `(label, arm_override_dict)` for every per-integration override in every spec."""
    for directory in SPEC_DIRS:
        for path in sorted((ROOT / "tests" / directory).glob("*.yml")):
            spec = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(spec, dict):
                continue
            for name, action in (spec.get("actions") or {}).items():
                if not isinstance(action, dict):
                    continue
                for arm in ARMS:
                    if arm in action and isinstance(action[arm], dict):
                        yield f"{path.name}:{name}:{arm}", action[arm]


def test_no_bunkerweb_setting_sits_outside_an_override_config_block():
    inspected = 0
    violations = []
    for label, override in _overrides():
        inspected += 1
        for key in override:
            if key.isupper():
                violations.append(f"{label}:{key}")
    assert inspected > 0, "the sweep matched no integration override — the spec layout changed, fix the matcher"
    assert not violations, f"settings written beside `config:` instead of inside it (silently dropped): {violations}"


def test_no_override_blanks_out_the_actions_whole_config():
    inspected = 0
    violations = []
    for label, override in _overrides():
        if "config" not in override:
            continue
        inspected += 1
        if override["config"] is None:
            violations.append(label)
    assert inspected > 0, "the sweep matched no override carrying `config:` — the spec layout changed, fix the matcher"
    assert not violations, f"`config:` left empty, which deletes the action's entire config on that arm: {violations}"


def _runs_on_linux(spec: dict, action: dict) -> bool:
    for scope in (action, spec):
        integrations = scope.get("integrations")
        if integrations is None:
            continue
        if isinstance(integrations, str):
            return integrations == "all"
        return "Linux" in integrations
    return True


def _effective_linux_config(spec: dict, action: dict) -> dict:
    """The config `generate.py` ends up writing for the Linux arm, `None` deletions applied."""
    merged = dict(spec.get("config") or {})
    merged |= (spec.get("Linux") or {}).get("config") or {}
    merged |= action.get("config") or {}
    merged |= (action.get("Linux") or {}).get("config") or {}
    return {key: value for key, value in merged.items() if value is not None}


def test_every_linux_action_serving_php_uses_the_local_socket():
    """The Linux analogue of `test_k8s_app_page_expectations.py`.

    `REMOTE_PHP` points at the `php-fpm` container from `tests/misc/docker/services.yml`, which
    only exists on the arms that share a Docker network with BunkerWeb. The Linux container runs
    `network_mode: host` and bind-mounts `/run/php`, so it serves the same `tests/misc/index.php`
    through `LOCAL_PHP=/run/php/php-fpm.sock` instead -- and every spec that reaches for PHP
    carries a `Linux:` override saying exactly that.

    Losing it is not a PHP failure: the location falls back to the reverse proxy, `app1` is
    `nginxdemos/nginx-hello`, and the `Hello World!` heading those specs assert (`<h1>` in
    index.php) is simply not on the page -- the same shape as the Kubernetes upstream trap its
    sibling sweep guards, one arm over.
    """
    served_locally = 0
    violations = []
    for directory in SPEC_DIRS:
        for path in sorted((ROOT / "tests" / directory).glob("*.yml")):
            spec = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(spec, dict):
                continue
            for name, action in (spec.get("actions") or {}).items():
                if not isinstance(action, dict) or not _runs_on_linux(spec, action):
                    continue
                config = _effective_linux_config(spec, action)
                if "REMOTE_PHP" in config:
                    violations.append(f"{path.name}:{name}")
                elif "LOCAL_PHP" in config:
                    served_locally += 1
    # The healthy state is zero matches, so the "did the matcher still work" anchor has to be the
    # other half: the actions that DO serve PHP over the local socket on Linux.
    assert served_locally > 0, "the sweep found no Linux action serving PHP at all — the spec layout changed, fix the matcher"
    assert not violations, f"Linux-running actions still pointing at the php-fpm container instead of the local socket: {violations}"


def test_the_linux_arm_receives_the_specs_api_environment():
    """A spec's `api:` block has to reach the Linux API, and only `api.env` carries it there.

    `bunkernet.yml` sets `API_USERNAME`/`API_PASSWORD` under `api:` and then authenticates
    against `/bunkernet/stats` with them. `generate.py` used to skip `write_env("api.env", ...)`
    on Linux, so the packaged API booted with the commented-out defaults its own start script
    writes, no bootstrap admin was ever created, and the call came back `401 Unauthorized` --
    with nothing in any log naming the missing credentials, because the Linux failure dump does
    not show the API's journal.

    Both halves are load-bearing and both are silent when removed, so pin them together.
    """
    generate = (ROOT / "tests" / "generate.py").read_text(encoding="utf-8")
    api_script = (ROOT / "src" / "linux" / "scripts" / "bunkerweb-api.sh").read_text(encoding="utf-8")

    assert 'write_env("api.env", config["api"])' in generate, "generate.py no longer writes api.env at all"
    assert 'if ARGS.integration not in ("Linux", "All-in-one"):\n        write_env("api.env"' not in generate, "api.env is gated off the Linux arm again"
    assert "export_env_file /etc/bunkerweb/api.env" in api_script, "the packaged API no longer sources /etc/bunkerweb/api.env"
