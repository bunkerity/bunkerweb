"""Raw mode must not post a setting that still has its default value (BW-566).

`plugins-settings.js` built the raw-mode form from the raw text, then appended every key of
`#raw-config-defaults` and of `#raw-entire-config` that the text did not carry. The second list holds
every setting of the page, so an untouched save posted all of them. Since 4fe1c9c56 the
`PERMISSIONS_POLICY` default contains `publickey-credentials-remote-client-data-json=()`, which CRS
942151 reads as the SQL function `json(`: on a UI behind BunkerWeb with ModSecurity on, a raw save of
a service or of the global config came back 403. Easy and advanced mode already skip unchanged
defaults (`shouldSkipUnchangedDefault`).

What the page may omit is only a setting whose method is `default` and whose value is the default:
the service routes restore nothing for an editable (`ui`) row, so a service override that equals the
setting default (global `USE_ANTIBOT=captcha`, service `USE_ANTIBOT=no`) is dropped when it is not
posted. The template therefore names the safe keys in `#raw-unchanged-defaults`, and the script skips
exactly those.

The script half runs the shipped loops in Node with stubs (skipped when Node is absent), the template
half renders the real template.
"""

import json
import re
import subprocess
from pathlib import Path
from shutil import which

import pytest
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / "src" / "ui" / "app"
SCRIPT = UI / "static" / "js" / "plugins-settings.js"
NVM_NODE = Path.home() / ".nvm" / "versions" / "node" / "v24.12.0" / "bin" / "node"
NODE = which("node") or (str(NVM_NODE) if NVM_NODE.exists() else None)

POLICY_DEFAULT = "accelerometer=(), publickey-credentials-remote-client-data-json=()"


def _block(text: str, opener: str) -> str:
    """The `opener(...).forEach(...);` statement, found by paren matching from the `.forEach(`."""
    start = text.index(opener)
    depth, i = 0, text.index("(", text.index(".forEach", start))
    while True:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 2]  # noqa: E203
        i += 1


def _run_loops(defaults: dict, originals: dict, raw_keys: dict, unchanged: list) -> dict:
    """Run the raw branch's two append loops on stubs and return what they posted, in order."""
    text = SCRIPT.read_text()
    branch = text[text.index('currentMode === "raw"') :]  # noqa: E203
    loops = _block(branch, "Object.entries(configDefaults)") + "\n" + _block(branch, "Object.entries(entireconfigOriginals)")
    assert NODE is not None
    program = f"""
const posted = [];
const appendHiddenInput = (form, name, value) => posted.push([name, value]);
const form = null;
const configDefaults = {json.dumps(defaults)};
const entireconfigOriginals = {json.dumps(originals)};
const rawUnchangedDefaults = new Set({json.dumps(unchanged)});
const formKeys = new Set({json.dumps(list(raw_keys))});
const skippedKeys = new Set();
{loops}
console.log(JSON.stringify(posted));
"""
    result = subprocess.run([NODE, "--input-type=commonjs", "-e", program], capture_output=True, text=True, timeout=60, check=True)
    return dict(json.loads(result.stdout))


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


@needs_node
def test_an_untouched_default_is_not_posted():
    posted = _run_loops(
        defaults={},
        originals={"PERMISSIONS_POLICY": POLICY_DEFAULT, "USE_ANTIBOT": "no", "SERVER_NAME": "www.example.com"},
        raw_keys={"SERVER_NAME": "www.example.com"},
        unchanged=["PERMISSIONS_POLICY"],
    )
    assert "PERMISSIONS_POLICY" not in posted


@needs_node
def test_a_service_override_equal_to_the_default_is_still_posted():
    """`USE_ANTIBOT` is `ui`-owned and equals its default, so the page does not list it as skippable."""
    posted = _run_loops(
        defaults={},
        originals={"PERMISSIONS_POLICY": POLICY_DEFAULT, "USE_ANTIBOT": "no"},
        raw_keys={},
        unchanged=["PERMISSIONS_POLICY"],
    )
    assert posted == {"USE_ANTIBOT": "no"}


@needs_node
def test_a_removed_non_default_setting_is_still_reset_to_its_default():
    posted = _run_loops(
        defaults={"USE_GZIP": "no"},
        originals={"USE_GZIP": "yes", "USE_BROTLI": "no"},
        raw_keys={},
        unchanged=["USE_BROTLI"],
    )
    assert posted == {"USE_GZIP": "no"}


@needs_node
def test_a_default_the_user_wrote_is_posted_once_as_written():
    posted = _run_loops(
        defaults={},
        originals={"PERMISSIONS_POLICY": POLICY_DEFAULT},
        raw_keys={"PERMISSIONS_POLICY": POLICY_DEFAULT},
        unchanged=["PERMISSIONS_POLICY"],
    )
    # The raw entries are posted before the loops run; neither loop posts the key a second time.
    assert posted == {}


def test_the_script_reads_the_skippable_keys_from_the_page():
    text = SCRIPT.read_text()
    assert 'id="raw-unchanged-defaults"' not in text
    assert re.search(r'\$\(\s*"#raw-unchanged-defaults"\s*\)', text), "the raw branch never reads #raw-unchanged-defaults"


# --- template half -------------------------------------------------------------------------------


def _setting(default="", **extra):
    return {"default": default, "type": "text", "regex": ".*", **extra}


def _render(config: dict, settings: dict, multiples: dict | None = None, endpoint: str = "services") -> str:
    env = Environment(loader=FileSystemLoader(str(UI / "templates")), autoescape=True)
    template = env.get_template("models/plugins_settings_raw.html")
    editable = {"default", "ui", "autoconf"}
    return template.render(
        config=config,
        plugins={"general": {"settings": settings}},
        get_filtered_settings=lambda plugin_settings, *_: plugin_settings,
        get_multiples=lambda *_: multiples or {},
        is_editable_method=lambda method, allow_default=False: method in editable and (allow_default or method != "default"),
        blacklisted_settings=[],
        current_endpoint=endpoint,
        csrf_token=lambda: "token",
        request=type("Request", (), {"is_secure": True})(),
        is_readonly=False,
        user_readonly=False,
        clone=False,
        raw_draft_config=None,
    )


def _field(html: str, field_id: str) -> str:
    match = re.search(rf'id="{field_id}"\s+(?:name="[^"]*"\s+)?value=(["\'])(.*?)\1', html, re.S)
    assert match, f"#{field_id} is not in the page"
    return match.group(2).replace("&#34;", '"').replace("&#39;", "'")


def _unchanged(html: str) -> set:
    return set(json.loads(_field(html, "raw-unchanged-defaults")))


def test_the_page_lists_only_default_method_defaults_as_skippable():
    settings = {
        "PERMISSIONS_POLICY": _setting(POLICY_DEFAULT),
        "USE_ANTIBOT": _setting("no"),
        "USE_GZIP": _setting("yes"),
        "USE_BROTLI": _setting("no"),
        "SERVER_NAME": _setting(""),
    }
    config = {
        "PERMISSIONS_POLICY": {"value": POLICY_DEFAULT, "method": "default"},
        # A ui row equal to the default: the service overrides a non-default global with it.
        "USE_ANTIBOT": {"value": "no", "method": "ui"},
        "USE_GZIP": {"value": "no", "method": "ui"},
        "USE_BROTLI": {"value": "no", "method": "default", "is_draft": True},
        "SERVER_NAME": {"value": "", "method": "default"},
    }
    html = _render(config, settings)
    assert _unchanged(html) == {"PERMISSIONS_POLICY"}
    # The preservation channel itself is unchanged: every setting stays in #raw-entire-config.
    entire = _field(html, "raw-entire-config")
    assert f"PERMISSIONS_POLICY={POLICY_DEFAULT}" in entire and "USE_ANTIBOT=no" in entire


def test_the_page_lists_default_method_multiples_too():
    settings = {"REVERSE_PROXY_HOST": _setting("", multiple="reverse-proxy")}
    config = {"REVERSE_PROXY_HOST_1": {"value": "", "method": "default"}}
    multiples = {"reverse-proxy": {1: {"REVERSE_PROXY_HOST_1": {**settings["REVERSE_PROXY_HOST"], "setting_no_suffix": "REVERSE_PROXY_HOST"}}}}
    html = _render(config, {}, multiples)
    assert _unchanged(html) == {"REVERSE_PROXY_HOST_1"}
