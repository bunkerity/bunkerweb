"""Generated fragments are discovered in staging; operator configs keep their own root."""

import logging
import re
import shutil
from glob import glob
from pathlib import Path

import pytest

import Templator as T
from Configurator import Configurator

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src/common/confs"
CORE = ROOT / "src/common/core"
SETTINGS = ROOT / "src/common/settings.json"
GLOBAL_CONTEXTS = ("global", "http", "stream", "default-server-http")
CONTEXTS = ("modsec", "modsec-crs", "crs-plugins-before", "crs-plugins-after")


@pytest.fixture
def staged(tmp_path, monkeypatch):
    final = tmp_path / "nginx"
    output = final / ".bw-gen.123"
    output.mkdir(parents=True)
    custom = tmp_path / "custom-configs"
    custom.mkdir()
    plugins = tmp_path / "plugins"
    pro_plugins = tmp_path / "pro-plugins"
    plugins.mkdir()
    pro_plugins.mkdir()
    for context in CONTEXTS:
        fragment = plugins / "fixture/confs" / context / "fixture.conf"
        fragment.parent.mkdir(parents=True)
        fragment.write_text("# generated plugin fragment\n")
    monkeypatch.setattr(T, "sep", str(tmp_path))

    # Sandbox literal roots at the filesystem boundary, leaving the real probe intact.
    def sandbox_glob(pattern):
        for literal, sandbox in (("/etc/nginx", final), ("/etc/bunkerweb/configs", custom)):
            if pattern.startswith(literal + "/"):
                pattern = str(sandbox / pattern.removeprefix(literal + "/"))
                break
        return glob(pattern)

    monkeypatch.setattr(T, "glob", sandbox_glob)

    def build(multisite, global_crs="no"):
        config = Configurator(
            str(SETTINGS),
            str(CORE),
            str(plugins),
            str(pro_plugins),
            {"SERVER_NAME": "new.example.com", "MULTISITE": multisite, "USE_MODSECURITY_GLOBAL_CRS": global_crs},
            logging.getLogger("staged-modsec"),
        ).get_config()
        return T.Templator(str(CONFS), str(CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy())

    return build, final, output, custom


@pytest.mark.parametrize("multisite", ["no", "yes"])
def test_first_staged_render_includes_every_generated_fragment_context(staged, multisite):
    build, final, output, _ = staged
    templator = build(multisite)
    # Real render includes the process-pool path used by generation.
    assert templator.render() == []
    service = "new.example.com/" if multisite == "yes" else ""
    rules = (output / service / "server-http/modsecurity-rules.conf.modsec").read_text()
    for context in CONTEXTS:
        assert not (final / service / context).exists()
        assert (output / service / context / "fixture.conf").is_file()
        assert templator._base_template_vars["is_custom_conf"](f"/etc/nginx/{service}{context}")
        assert f"include /etc/nginx/{service}{context}/*.conf" in rules.splitlines()
    assert ".bw-gen." not in rules


@pytest.mark.parametrize("context", CONTEXTS)
def test_stale_final_fragments_do_not_count_as_current_output(staged, context):
    build, final, _, _ = staged
    stale = final / context / "removed.conf"
    stale.parent.mkdir()
    stale.touch()
    templator = build("no")
    assert not templator._base_template_vars["is_custom_conf"](f"/etc/nginx/{context}")


def test_operator_config_probe_stays_literal(staged):
    build, _, output, custom = staged
    generated = output / "modsec"
    generated.mkdir()
    (generated / "generated.conf").touch()
    probe = build("no")._base_template_vars["is_custom_conf"]
    assert not probe("/etc/bunkerweb/configs/modsec")
    operator = custom / "modsec"
    operator.mkdir()
    (operator / "operator.conf").touch()
    assert probe("/etc/bunkerweb/configs/modsec")


@pytest.mark.parametrize("multisite", ["no", "yes"])
def test_staged_render_keeps_operator_and_generated_after_includes_separate(staged, multisite):
    build, _, output, custom = staged
    service = "new.example.com"
    scopes = [""] + ([service] if multisite == "yes" else [])
    for scope in scopes:
        operator = custom / "crs-plugins-after" / scope
        operator.mkdir(parents=True)
        (operator / "operator.conf").write_text("# operator after rules\n")
    assert build(multisite).render() == []
    rules = (output / (service if multisite == "yes" else "") / "server-http/modsecurity-rules.conf.modsec").read_text().splitlines()
    expected = [f"include /etc/bunkerweb/configs/crs-plugins-after/{scope + '/' if scope else ''}*.conf" for scope in scopes]
    expected.append(f"include /etc/nginx/{service + '/' if multisite == 'yes' else ''}crs-plugins-after/*.conf")
    assert [line for line in rules if "crs-plugins-after/" in line] == expected


@pytest.mark.parametrize("global_crs", ["no", "yes"])
@pytest.mark.parametrize("multisite", ["no", "yes"])
@pytest.mark.parametrize("operator,generated", [(False, False), (True, False), (False, True), (True, True)])
def test_after_include_condition_matrix_preserves_lines(staged, global_crs, multisite, operator, generated):
    build, _, output, _ = staged
    templator = build(multisite, global_crs)
    present = []
    if operator:
        present.append("/etc/bunkerweb/configs/crs-plugins-after")
        if global_crs == "no" and multisite == "yes":
            present.append("/etc/bunkerweb/configs/crs-plugins-after/new.example.com")
    if generated:
        present.append("/etc/nginx/crs-plugins-after")
        if global_crs == "no" and multisite == "yes":
            present.append("/etc/nginx/new.example.com/crs-plugins-after")
    template = "http/modsecurity-rules-global-crs.conf.modsec" if global_crs == "yes" else "server-http/modsecurity-rules.conf.modsec"
    variables = templator._base_template_vars | templator._config | {"all": templator._full_config, "is_custom_conf": lambda path: path.rstrip("/") in present}
    assert templator._render_template(template, variables)
    lines = (output / template).read_text().splitlines()
    assert "# custom CRS plugins configurations after loading plugins" in lines
    assert [line for line in lines if "crs-plugins-after/" in line] == [f"include {path}/*.conf" for path in present]


def test_global_crs_single_site_includes_plugin_fragments_on_every_render(staged):
    build, final, output, _ = staged
    expected = [f"include /etc/nginx/{context}/*.conf" for context in ("crs-plugins-before", "modsec-crs", "crs-plugins-after")]
    for render in range(2):
        assert build("no", "yes").render() == []
        rules = (output / "http/modsecurity-rules-global-crs.conf.modsec").read_text().splitlines()
        assert [line for line in rules if line.startswith("include /etc/nginx/") and "/http/" not in line] == expected, f"render {render}"
        # Publish this render, like the generator's directory swap, then render again over it.
        shutil.copytree(output, final, dirs_exist_ok=True)
        shutil.rmtree(output)
        output.mkdir()


def test_global_crs_single_site_drops_fragments_a_plugin_stopped_shipping(staged, tmp_path):
    build, final, output, _ = staged
    for context in ("modsec-crs", "crs-plugins-before", "crs-plugins-after"):
        # Previous render published the fragment, the plugin no longer ships it.
        stale = final / context / "fixture.conf"
        stale.parent.mkdir()
        stale.touch()
        (tmp_path / "plugins/fixture/confs" / context / "fixture.conf").unlink()
    assert build("no", "yes").render() == []
    rules = (output / "http/modsecurity-rules-global-crs.conf.modsec").read_text()
    assert "include /etc/nginx/crs-plugins-" not in rules
    # Core plugins still ship modsec-crs fragments, so only the plugin-shipped file leaves the staged folder.
    assert not (output / "modsec-crs/fixture.conf").exists()
    assert "include /etc/nginx/modsec-crs/*.conf" in rules


def test_server_templates_probe_the_global_output_of_the_same_render(staged, tmp_path):
    build, _, output, _ = staged
    probe = tmp_path / "plugins/fixture/confs/server-http/fixture-probe.conf"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text('{{ "global output present" if is_custom_conf("/etc/nginx/http") else "global output missing" }}\n')
    assert build("no").render() == []
    assert (output / "server-http/fixture-probe.conf").read_text() == "global output present\n"


def _core_global_templates_probing_staged_folders():
    """Global-context templates under the core confs that probe a staged /etc/nginx folder."""
    probing = set()
    for confs in (CONFS, *CORE.glob("*/confs")):
        for template in confs.rglob("*"):
            relative = template.relative_to(confs).as_posix()
            context = relative.split("/", 1)[0] if "/" in relative else "global"
            if template.is_file() and context in GLOBAL_CONTEXTS and re.search(r'is_custom_conf\(\s*["\']/etc/nginx/', template.read_text(errors="ignore")):
                probing.add(relative)
    return probing


def test_global_templates_probing_staged_folders_are_deferred():
    assert _core_global_templates_probing_staged_folders() == T.DEFERRED_GLOBAL_TEMPLATES
