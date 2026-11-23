"""Size bound and chunked-marker semantics of the core Host regexes in ui.modsec-crs, antibot.modsec-crs and ip-host.modsec-crs.

libModSecurity 3.0.17 (core 1.6.18) refuses to load an @rx operand whose compiled form passes PCRE2's 64 KiB link-size
limit (about 1,000 host names), so a rules file with a bigger Host list fails `nginx -t`. The templates keep the single
Host regex up to HOST_CAP bytes and switch to phase-1 marker rules past it. These tests render the real templates the way
the Templator does (trim_blocks, lstrip_blocks) and evaluate the rendered rules with a small interpreter.
"""

from importlib import import_module
from os import environ
from pathlib import Path
import re

import pytest

jinja2 = pytest.importorskip("jinja2")

ROOT = Path(__file__).resolve().parents[2]
# *_TEMPLATE lets a reviewer point a test at a copy of the template from another revision.
UI_TEMPLATE = Path(environ.get("UI_MODSEC_CRS_TEMPLATE", ROOT / "src/common/core/ui/confs/http/ui.modsec-crs"))
ANTIBOT_TEMPLATE = Path(environ.get("ANTIBOT_MODSEC_CRS_TEMPLATE", ROOT / "src/common/core/antibot/confs/http/antibot.modsec-crs"))
IP_HOST_TEMPLATE = Path(environ.get("IP_HOST_MODSEC_CRS_TEMPLATE", ROOT / "src/common/core/modsecurity/confs/http/ip-host.modsec-crs"))
GOLDEN = Path(__file__).parent / "fixtures" / "core_host_modsec_crs"

HOST_CAP = 8192
MAX_CHUNKS = 100
# Ledger blocks: ui 9,802,000 (rules 100-112, UI markers 200-299, IP markers 300-399), antibot 9,801,000 (markers 100-199, allow rule 500).
UI_ID_RANGE = (9802100, 9802399)
ANTIBOT_ID_RANGE = (9801100, 9801599)
ANTIBOT_ALLOW_ID = "9801500"
# modsecurity block 9,800,000: ip-host rule 100, ip-host markers 300-399.
IP_HOST_RULE_ID = "9800100"
IP_HOST_ID_RANGE = (9800100, 9800399)
ANTIBOT_URI = "/challenge"

# Every ui rule that reuses the host list: id -> (method, a path its URL guard accepts).
UI_RULES = {
    "9802100": ("GET", "/"),
    "9802101": ("GET", "/services/a"),
    "9802102": ("GET", "/cache/a"),
    "9802103": ("GET", "/configs/a"),
    "9802112": ("POST", "/configs/new"),
    "9802104": ("GET", "/logs"),
    "9802105": ("GET", "/plugins/a"),
    "9802106": ("GET", "/fonts/a"),
    "9802107": ("GET", "/"),
    "9802108": ("GET", "/login"),
    "9802109": ("GET", "/instances/new"),
    "9802110": ("GET", "/reports/fetch"),
}
UI_IP_RULE = ("9802111", "GET", "/")


def has_variable(all_vars: dict, variable: str, value: str) -> bool:
    """Mirror of Templator.has_variable (src/common/gen/Templator.py)."""
    if all_vars.get(variable) == value:
        return True
    if all_vars.get("MULTISITE", "no") == "yes":
        return any(all_vars.get(f"{name}_{variable}") == value for name in all_vars.get("SERVER_NAME", "").strip().split())
    return False


def _render(path: Path, all_vars: dict, trim: bool = True) -> str:
    env = jinja2.Environment(undefined=jinja2.ChainableUndefined, lstrip_blocks=trim, trim_blocks=trim, keep_trailing_newline=True)  # nosec B701
    env.globals["import"] = import_module
    env.globals["has_variable"] = has_variable
    return env.from_string(path.read_text(encoding="utf-8")).render(all=all_vars, **all_vars)


def render_ui(services: dict, trim: bool = True) -> str:
    """services maps a service id to (USE_UI, SERVER_NAME)."""
    all_vars = {"MULTISITE": "yes", "SERVER_NAME": " ".join(services), "USE_UI": "no"}
    for service_id, (use_ui, names) in services.items():
        all_vars[f"{service_id}_USE_UI"] = use_ui
        all_vars[f"{service_id}_SERVER_NAME"] = names
    return _render(UI_TEMPLATE, all_vars, trim)


def render_antibot(services: dict, trim: bool = True) -> str:
    """services maps a service id to (USE_ANTIBOT, SERVER_NAME)."""
    all_vars = {"MULTISITE": "yes", "SERVER_NAME": " ".join(services), "USE_ANTIBOT": "no", "ANTIBOT_URI": ANTIBOT_URI}
    for service_id, (antibot, names) in services.items():
        all_vars[f"{service_id}_USE_ANTIBOT"] = antibot
        all_vars[f"{service_id}_SERVER_NAME"] = names
    return _render(ANTIBOT_TEMPLATE, all_vars, trim)


def render_antibot_single_site(names: str, antibot: str = "captcha") -> str:
    return _render(ANTIBOT_TEMPLATE, {"MULTISITE": "no", "SERVER_NAME": names, "USE_ANTIBOT": antibot, "ANTIBOT_URI": ANTIBOT_URI})


def render_ip_host(services: dict = None, single: str = None, trim: bool = True) -> str:
    """services maps a service id to its SERVER_NAME (multisite); single is the SERVER_NAME of a single-site install."""
    all_vars = {"USE_MODSECURITY": "yes", "USE_MODSECURITY_CRS": "yes", "USE_MODSECURITY_GLOBAL_CRS": "yes"}
    if services is not None:
        all_vars.update({"MULTISITE": "yes", "SERVER_NAME": " ".join(services)})
        all_vars.update({f"{service_id}_SERVER_NAME": names for service_id, names in services.items()})
    else:
        all_vars.update({"MULTISITE": "no", "SERVER_NAME": single})
    return _render(IP_HOST_TEMPLATE, all_vars, trim)


def names(count: int, prefix: str, length: int = 0) -> list:
    """Distinct synthetic names of realistic shape (dotted and hyphenated); length > 0 pads each one to about that many bytes."""
    out = []
    for i in range(count):
        label = f"{prefix}{i:05d}-board.sample" if i % 2 else f"{prefix}{i:05d}.library.edu-demo"
        if length:
            label = f"{'a' * max(1, length - len(label) - 8)}.{label}"
        out.append(f"{label}.example.test")
    return out


def ips(count: int, a: int = 10) -> list:
    return [f"{a}.{(i >> 16) & 255}.{(i >> 8) & 255}.{i & 255}" for i in range(1, count + 1)]


def operands(rendered: str) -> list:
    return [m.group(1) for m in re.finditer(r'"@rx ([^"]*)"', rendered)]


def rule_ids(rendered: str) -> list:
    return re.findall(r"id:(\d+)", rendered)


# --- a small interpreter for the rendered rules -------------------------------------------------------------------


def parse(rendered: str) -> list:
    """Return chains [(id, [(variable, operator, argument, transformations, setvars), ...]), ...] in file order."""
    text = re.sub(r"\\\n\s*", " ", rendered)
    chains, current, chain_id = [], None, None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r'SecRule (\S+) "(@\w+) ?(.*?)"\s+"(.*)"', line)
        assert m, f"unparsable rule line: {line[:120]}"
        variable, operator, argument, actions = m.groups()
        actions = [a.strip() for a in actions.split(",") if a.strip()]
        if current is None:
            current = []
            ids = [a[3:] for a in actions if a.startswith("id:")]
            assert len(ids) == 1, line[:120]
            chain_id = ids[0]
        trans = [a[2:] for a in actions if a.startswith("t:")]
        setvars = [a.removeprefix("setvar:") for a in actions if a.startswith("setvar:")]
        current.append((variable, operator, argument, trans, setvars))
        if "chain" not in actions:
            chains.append((chain_id, current))
            current = None
    assert current is None, "dangling chain"
    return chains


def fired(rendered_or_chains, method: str, path: str, host: str) -> set:
    chains = parse(rendered_or_chains) if isinstance(rendered_or_chains, str) else rendered_or_chains
    tx, hits = {}, set()
    for chain_id, links in chains:
        pending = {}
        for variable, operator, argument, trans, setvars in links:
            if variable == "REQUEST_FILENAME":
                value = path
            elif variable == "REQUEST_METHOD":
                value = method
            elif variable == "REQUEST_HEADERS:Host":
                value = host
            elif variable.startswith("TX:"):
                value = str(tx.get(variable[3:], ""))
            else:
                raise AssertionError(variable)
            for t in trans:
                if t == "lowercase":
                    value = value.lower()
                elif t not in ("none", "normalizePath"):
                    pytest.fail(f"transformation {t}")
            if operator == "@rx":
                ok = re.search(argument, value) is not None
            elif operator in ("@streq", "@eq"):
                ok = value == argument
            elif operator == "@endsWith":
                ok = value.endswith(argument)
            else:
                raise AssertionError(operator)
            if not ok:
                break
            pending.update(dict(sv.split("=", 1) for sv in setvars))
        else:
            hits.add(chain_id)
            tx.update({k.removeprefix("tx."): v for k, v in pending.items()})
    return hits


def ui_exempt(chains, host: str) -> bool:
    """True when every rule that reuses the UI host list fires for this host on its own URL."""
    results = {fired(chains, method, path, host) >= {rid} for rid, (method, path) in UI_RULES.items()}
    assert len(results) == 1, f"the rules disagree about {host}"
    return results.pop()


def ip_exempt(chains, host: str) -> bool:
    rid, method, path = UI_IP_RULE
    return rid in fired(chains, method, path, host)


def antibot_allowed(chains, host: str, path: str = ANTIBOT_URI) -> bool:
    return ANTIBOT_ALLOW_ID in fired(chains, "GET", path, host)


# --- shapes ---------------------------------------------------------------------------------------------------------


def ui_shape(name: str) -> dict:
    if name == "S1":  # client shape: every service is a UI service, ~1,570 names
        return {
            "default.app": ("yes", " ".join(["default.app"] + names(1149, "a"))),
            "svc2.example.test": ("yes", " ".join(names(420, "b"))),
            "svc3.example.test": ("yes", "svc3.example.test"),
            "svc4.example.test": ("yes", " ".join(names(3, "c"))),
        }
    if name == "S2":  # one small UI service, ~1,500 non-UI names
        return {
            "ui.example.test": ("yes", "ui.example.test ui-alt.example.test www.ui.example.test"),
            "a.example.test": ("no", " ".join(names(700, "d"))),
            "b.example.test": ("no", " ".join(names(500, "e"))),
            "c.example.test": ("no", " ".join(names(300, "f"))),
        }
    if name == "S3":  # 5,000 names, all UI
        return {f"s{i}.example.test": ("yes", " ".join(names(1250, f"g{i}"))) for i in range(4)}
    if name == "S3ip":  # a UI host plus 3,000 UI IP literals
        return {"ui.example.test": ("yes", " ".join(["ui.example.test"] + ips(3000)))}
    raise KeyError(name)


# --- size bound -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["S1", "S2", "S3", "S3ip"])
def test_ui_no_rx_operand_exceeds_the_cap_whatever_the_number_of_names(name):
    rendered = render_ui(ui_shape(name))

    sizes = [len(op.encode()) for op in operands(rendered)]
    assert sizes and max(sizes) <= HOST_CAP, max(sizes)
    ids = rule_ids(rendered)
    assert len(ids) == len(set(ids)) and all(UI_ID_RANGE[0] <= int(i) <= UI_ID_RANGE[1] for i in ids), ids


@pytest.mark.parametrize("name", ["S1", "S2", "S3"])
def test_antibot_no_rx_operand_exceeds_the_cap_whatever_the_number_of_names(name):
    rendered = render_antibot({sid: ("captcha", n) for sid, (_, n) in ui_shape(name).items()})  # antibot on every service

    sizes = [len(op.encode()) for op in operands(rendered)]
    assert sizes and max(sizes) <= HOST_CAP, max(sizes)
    ids = rule_ids(rendered)
    assert len(ids) == len(set(ids)) and all(ANTIBOT_ID_RANGE[0] <= int(i) <= ANTIBOT_ID_RANGE[1] for i in ids), ids
    assert ANTIBOT_ALLOW_ID in ids


def test_antibot_single_site_names_are_bounded_too():
    rendered = render_antibot_single_site(" ".join(names(3000, "m")))

    assert max(len(op.encode()) for op in operands(rendered)) <= HOST_CAP
    assert antibot_allowed(parse(rendered), names(3000, "m")[1500])


def test_markers_come_before_the_rules_that_test_them_and_set_one_variable_each():
    ui = render_ui({**ui_shape("S3"), "ip.example.test": ("yes", " ".join(ips(3000)))})
    ids = [int(i) for i in rule_ids(ui)]
    first_consumer = ui.index("id:9802100")
    assert all(ui.index(f"id:{i}") < first_consumer for i in ids if 9802200 <= i < 9802300)
    assert all(ui.index(f"id:{i}") < ui.index("id:9802111") for i in ids if 9802300 <= i < 9802400)
    assert set(re.findall(r"setvar:(\S+?)=", ui)) == {"tx.bw_ui_host", "tx.bw_ui_ip_host"}

    antibot = render_antibot({sid: ("captcha", n) for sid, (_, n) in ui_shape("S3").items()})
    assert set(re.findall(r"setvar:(\S+?)=", antibot)) == {"tx.bw_antibot_host"}
    assert all(antibot.index(f"id:{i}") < antibot.index(f"id:{ANTIBOT_ALLOW_ID}") for i in rule_ids(antibot) if i != ANTIBOT_ALLOW_ID)


def test_the_templates_render_the_same_rules_with_and_without_trim_blocks():
    def normalized(text):
        return [line.strip() for line in re.sub(r"\\\n", "\\ ", text).splitlines() if line.strip()]

    for name in ("S1", "S3ip"):
        assert normalized(render_ui(ui_shape(name), trim=True)) == normalized(render_ui(ui_shape(name), trim=False))
    all_on = {sid: ("captcha", n) for sid, (_, n) in ui_shape("S1").items()}
    assert normalized(render_antibot(all_on, trim=True)) == normalized(render_antibot(all_on, trim=False))


# --- small installs stay byte-identical ------------------------------------------------------------------------------

UI_SMALL = {
    "ui.example.test": ("yes", "ui.example.test Www.UI.example.test 10.0.0.5 2001:db8::1 [2001:db8::2]"),
    "o.example.test": ("no", "o.example.test www.o.example.test"),
}
ANTIBOT_SMALL = {
    "a.example.test": ("captcha", "a.example.test www.a.example.test 2001:db8::1"),
    "b.example.test": ("no", "b.example.test"),
}


@pytest.mark.parametrize(
    "golden, rendered",
    [
        ("ui-small.modsec-crs", lambda: render_ui(UI_SMALL)),
        ("antibot-small.modsec-crs", lambda: render_antibot(ANTIBOT_SMALL)),
        ("antibot-single-site-small.modsec-crs", lambda: render_antibot_single_site("www.example.com 192.0.2.10 2001:db8::1")),
    ],
)
def test_a_small_install_renders_byte_identical_to_the_pre_chunking_template(golden, rendered):
    assert rendered() == (GOLDEN / golden).read_text()


def test_a_small_install_has_no_marker_rule():
    for rendered in (render_ui(UI_SMALL), render_antibot(ANTIBOT_SMALL)):
        assert "setvar" not in rendered and "TX:" not in rendered
    assert rule_ids(render_ui(UI_SMALL)) == [f"98021{n:02d}" for n in (0, 1, 2, 3, 12, 4, 5, 6, 7, 8, 9, 10, 11)]
    assert rule_ids(render_antibot(ANTIBOT_SMALL)) == [ANTIBOT_ALLOW_ID]


# --- semantics --------------------------------------------------------------------------------------------------------

UI_CASES = [
    ("ui.example.test", True),
    ("UI.Example.TEST", True),
    ("ui.example.test:8443", True),
    ("WWW.UI.EXAMPLE.TEST:8443", True),
    ("o.example.test", False),
    ("o.example.test:8443", False),
    ("www.o.example.test", False),
    ("unknown.example.test", False),
    ("evil-ui.example.test", False),
    ("xui.example.test", False),
    ("ui.example.test.evil", False),
    ("ui.example.test:80a", False),
    ("10.0.0.5", False),  # IP names never match the name rules
]
IP_CASES = [
    ("10.0.0.5", True),
    ("10.0.0.5:8443", True),
    ("[2001:db8::1]", True),
    ("[2001:DB8::2]:8443", True),
    ("10.0.0.6", False),
    ("110.0.0.5", False),
    ("ui.example.test", False),
]


def ui_padded(ui_count: int, ip_count: int, length: int = 0) -> dict:
    services = dict(UI_SMALL)
    services["pad.example.test"] = ("yes", " ".join(names(ui_count, "p", length) + ips(ip_count, 172)))
    services["pad-other.example.test"] = ("no", " ".join(names(2000, "q")))
    return services


@pytest.mark.parametrize("host, expected", UI_CASES)
def test_ui_semantics_of_the_small_install(host, expected):
    chains = parse(render_ui(UI_SMALL))
    assert ui_exempt(chains, host) is expected


@pytest.mark.parametrize("host, expected", IP_CASES)
def test_ui_ip_semantics_of_the_small_install(host, expected):
    assert ip_exempt(parse(render_ui(UI_SMALL)), host) is expected


@pytest.mark.parametrize("ui_count, ip_count", [(2000, 3), (3, 2000), (2500, 2500)])
@pytest.mark.parametrize("host, expected", UI_CASES)
def test_ui_semantics_survive_chunking(host, expected, ui_count, ip_count):
    rendered = render_ui(ui_padded(ui_count, ip_count))

    assert "setvar" in rendered and max(len(o.encode()) for o in operands(rendered)) <= HOST_CAP
    assert ui_exempt(parse(rendered), host) is expected


@pytest.mark.parametrize("ui_count, ip_count", [(2000, 3), (3, 2000), (2500, 2500)])
@pytest.mark.parametrize("host, expected", IP_CASES)
def test_ui_ip_semantics_survive_chunking(host, expected, ui_count, ip_count):
    assert ip_exempt(parse(render_ui(ui_padded(ui_count, ip_count))), host) is expected


def test_ui_hosts_in_the_first_middle_and_last_chunk_are_exempt():
    chains = parse(render_ui(ui_padded(3000, 3000)))
    pad, pad_ips = names(3000, "p"), ips(3000, 172)

    assert all(ui_exempt(chains, host) for host in (pad[0], pad[1500], pad[-1], pad[-1].upper() + ":8443"))
    assert not ui_exempt(chains, "p99999.library.edu-demo.example.test")
    assert all(ip_exempt(chains, host) for host in (pad_ips[0], pad_ips[1500], pad_ips[-1] + ":9000"))
    assert not ip_exempt(chains, "172.200.0.1")
    # a UI name is never an IP exemption and the other way round
    assert not ip_exempt(chains, pad[0]) and not ui_exempt(chains, pad_ips[0])


def test_ui_every_rule_keeps_its_own_url_and_method_guard():
    chains = parse(render_ui(ui_padded(2000, 3)))

    assert fired(chains, "GET", "/configs/new", "ui.example.test") >= {"9802103"}
    assert "9802112" not in fired(chains, "GET", "/configs/new", "ui.example.test")  # POST only
    assert "9802112" in fired(chains, "POST", "/configs/new", "ui.example.test")
    assert {i for i in fired(chains, "GET", "/nothing", "ui.example.test") if int(i) < 9802200} == {"9802100", "9802107"}
    assert not {i for i in fired(chains, "GET", "/configs/a", "o.example.test") if int(i) < 9802200}


def test_ui_past_the_bound_extra_hosts_lose_the_exceptions_and_nothing_else_changes():
    # 4,200 names of 200 bytes: ~40 per chunk, so past 100 chunks the tail has no marker.
    services = {"pad.example.test": ("yes", " ".join(names(4200, "p", length=200) + ["ui.example.test"]))}
    rendered = render_ui(services)
    chains = parse(rendered)
    pad = names(4200, "p", 200)

    assert len([i for i in rule_ids(rendered) if 9802200 <= int(i) < 9802300]) == MAX_CHUNKS
    assert max(len(o.encode()) for o in operands(rendered)) <= HOST_CAP
    assert ui_exempt(chains, pad[0])
    assert not ui_exempt(chains, pad[-1])
    assert not ui_exempt(chains, "o.example.test")


def test_ui_an_oversized_name_is_skipped_and_the_others_keep_the_exceptions():
    huge = "h" * (HOST_CAP + 10) + ".example.test"
    chains = parse(render_ui({"ui.example.test": ("yes", " ".join([huge, "ui.example.test"] + names(1000, "u")))}))

    assert ui_exempt(chains, "ui.example.test") and not ui_exempt(chains, huge)


ANTIBOT_CASES = [
    ("a.example.test", True),
    ("A.Example.TEST:8443", True),
    ("www.a.example.test", True),
    ("[2001:db8::1]", True),
    ("[2001:DB8::1]:8443", True),
    ("b.example.test", False),  # service with antibot off
    ("unknown.example.test", False),
    ("xa.example.test", False),
    ("a.example.test.evil", False),
    ("a.example.test:80a", False),
]


def antibot_padded(count: int, length: int = 0) -> dict:
    services = dict(ANTIBOT_SMALL)
    services["pad.example.test"] = ("captcha", " ".join(names(count, "p", length)))
    services["pad-off.example.test"] = ("no", " ".join(names(2000, "q")))
    return services


@pytest.mark.parametrize("host, expected", ANTIBOT_CASES)
def test_antibot_semantics_of_the_small_install(host, expected):
    assert antibot_allowed(parse(render_antibot(ANTIBOT_SMALL)), host) is expected


@pytest.mark.parametrize("count", [1500, 3000, 5000])
@pytest.mark.parametrize("host, expected", ANTIBOT_CASES)
def test_antibot_semantics_survive_chunking(host, expected, count):
    rendered = render_antibot(antibot_padded(count))

    assert "setvar" in rendered and max(len(o.encode()) for o in operands(rendered)) <= HOST_CAP
    assert antibot_allowed(parse(rendered), host) is expected


def test_antibot_hosts_in_the_first_middle_and_last_chunk_are_allowed_and_disabled_ones_are_not():
    chains = parse(render_antibot(antibot_padded(3000)))
    pad, off = names(3000, "p"), names(2000, "q")

    assert all(antibot_allowed(chains, host) for host in (pad[0], pad[1500], pad[-1], pad[-1].upper() + ":8443"))
    assert not any(antibot_allowed(chains, host) for host in (off[0], off[1000], off[-1]))
    assert not antibot_allowed(chains, "p99999.library.edu-demo.example.test")


def test_antibot_only_the_challenge_uri_is_allowed():
    chains = parse(render_antibot(antibot_padded(3000)))

    assert antibot_allowed(chains, "a.example.test") and not antibot_allowed(chains, "a.example.test", "/other")
    assert not antibot_allowed(chains, "a.example.test", ANTIBOT_URI + "/x")


def test_antibot_past_the_bound_extra_hosts_are_not_allowed_and_nothing_else_changes():
    services = {"pad.example.test": ("captcha", " ".join(names(4200, "p", length=200)))}
    rendered = render_antibot(services)
    chains = parse(rendered)
    pad = names(4200, "p", 200)

    assert len([i for i in rule_ids(rendered) if 9801100 <= int(i) < 9801200]) == MAX_CHUNKS
    assert max(len(o.encode()) for o in operands(rendered)) <= HOST_CAP
    assert antibot_allowed(chains, pad[0]) and not antibot_allowed(chains, pad[-1]) and not antibot_allowed(chains, "o.example.test")


# --- ip-host.modsec-crs ------------------------------------------------------------------------------------------------

IP_HOST_SMALL = {"a.example.test": "a.example.test 10.0.0.5 10.0.0.5 2001:db8::1 192.0.2.7", "b.example.test": "b.example.test"}
IP_HOST_CASES = [
    ("10.0.0.5", True),
    ("10.0.0.5:8443", True),
    ("192.0.2.7", True),
    ("[2001:db8::1]", True),
    ("[2001:DB8::1]:8443", True),
    ("10.0.0.6", False),
    ("110.0.0.5", False),
    ("10.0.0.50", False),
    ("10.0.0.5x", False),
    ("a.example.test", False),
    ("unknown.example.test", False),
]


def ips6(count: int) -> list:
    """Bare IPv6 literals written out in full (the longest shape a service name takes)."""
    return [f"2001:0db8:{(i >> 16) & 0xFFFF:04x}:{i & 0xFFFF:04x}:0000:0000:0000:0001" for i in range(1, count + 1)]


def ip_host_exempt(chains, host: str) -> bool:
    return IP_HOST_RULE_ID in fired(chains, "GET", "/", host)


def ip_host_shape(name: str) -> dict:
    if name == "S3ip":  # 3,000 IPv4 literals: one regex of 41,137 bytes before the bound
        return {"ip.example.test": " ".join(["ip.example.test"] + ips(3000))}
    if name == "mixed":  # several services, names and IPv4 and IPv6 literals
        return {
            "a.example.test": " ".join(names(300, "a") + ips(1200, 172)),
            "b.example.test": " ".join(ips6(500) + names(200, "b")),
            "c.example.test": " ".join(ips(800, 10)),
        }
    raise KeyError(name)


@pytest.mark.parametrize("name", ["S3ip", "mixed"])
def test_ip_host_no_rx_operand_exceeds_the_cap_whatever_the_number_of_literals(name):
    rendered = render_ip_host(ip_host_shape(name))

    sizes = [len(op.encode()) for op in operands(rendered)]
    assert len(sizes) > 1 and max(sizes) <= HOST_CAP, max(sizes)
    ids = rule_ids(rendered)
    assert len(ids) == len(set(ids)) and all(IP_HOST_ID_RANGE[0] <= int(i) <= IP_HOST_ID_RANGE[1] for i in ids), ids
    assert IP_HOST_RULE_ID in ids


def test_ip_host_single_site_literals_are_bounded_too():
    rendered = render_ip_host(single=" ".join(ips(3000)))

    assert max(len(op.encode()) for op in operands(rendered)) <= HOST_CAP
    assert ip_host_exempt(parse(rendered), ips(3000)[1500])


def test_ip_host_markers_come_before_the_rule_that_tests_them_and_set_one_variable():
    rendered = render_ip_host(ip_host_shape("S3ip"))
    ids = rule_ids(rendered)

    assert ids[-1] == IP_HOST_RULE_ID and all(int(i) >= 9800300 for i in ids[:-1])
    assert set(re.findall(r"setvar:(\S+?)=", rendered)) == {"tx.bw_ip_host"}


def test_ip_host_renders_the_same_rules_with_and_without_trim_blocks():
    def normalized(text):
        return [line.strip() for line in re.sub(r"\\\n", "\\ ", text).splitlines() if line.strip()]

    for name in ("S3ip", "mixed"):
        assert normalized(render_ip_host(ip_host_shape(name), trim=True)) == normalized(render_ip_host(ip_host_shape(name), trim=False))


@pytest.mark.parametrize(
    "golden, rendered",
    [
        (
            "ip-host-small.modsec-crs",
            lambda: render_ip_host(
                {"a.example.test": "a.example.test 10.0.0.5 10.0.0.5 2001:db8::1 [2001:db8::2] 192.0.2.7", "b.example.test": "b.example.test"}
            ),
        ),
        ("ip-host-single-site-small.modsec-crs", lambda: render_ip_host(single="10.1.1.1 www.example.com 2001:db8::1")),
    ],
)
def test_ip_host_a_small_install_renders_byte_identical_to_the_pre_chunking_template(golden, rendered):
    assert rendered() == (GOLDEN / golden).read_text()


def test_ip_host_a_small_install_has_no_marker_rule_and_nothing_renders_without_a_literal():
    rendered = render_ip_host(IP_HOST_SMALL)

    assert "setvar" not in rendered and "TX:" not in rendered and rule_ids(rendered) == [IP_HOST_RULE_ID]
    assert render_ip_host({"a.example.test": "a.example.test www.example.test"}).strip() == ""


@pytest.mark.parametrize("host, expected", IP_HOST_CASES)
def test_ip_host_semantics_of_the_small_install(host, expected):
    assert ip_host_exempt(parse(render_ip_host(IP_HOST_SMALL)), host) is expected


def ip_host_padded(ip_count: int, ip6_count: int = 0) -> dict:
    return {**IP_HOST_SMALL, "pad.example.test": " ".join(ips(ip_count, 172) + ips6(ip6_count))}


@pytest.mark.parametrize("ip_count, ip6_count", [(2000, 0), (3, 1000), (1500, 1500)])
@pytest.mark.parametrize("host, expected", IP_HOST_CASES)
def test_ip_host_semantics_survive_chunking(host, expected, ip_count, ip6_count):
    rendered = render_ip_host(ip_host_padded(ip_count, ip6_count))

    assert "setvar" in rendered and max(len(o.encode()) for o in operands(rendered)) <= HOST_CAP
    assert ip_host_exempt(parse(rendered), host) is expected


def test_ip_host_literals_in_the_first_middle_and_last_chunk_get_the_exception_and_others_do_not():
    chains = parse(render_ip_host(ip_host_padded(3000, 600)))
    v4, v6 = ips(3000, 172), ips6(600)

    assert all(
        ip_host_exempt(chains, host) for host in ("10.0.0.5", v4[0], v4[1500], v4[-1] + ":9000", f"[{v6[0]}]", f"[{v6[300]}]", f"[{v6[-1].upper()}]:8443")
    )
    assert not any(ip_host_exempt(chains, host) for host in ("172.200.0.1", "10.0.0.6", "[2001:db8::99]", "a.example.test", "172.0.99.99"))


def test_ip_host_the_first_service_id_is_the_name_when_it_has_no_server_name_and_duplicates_collapse():
    rendered = render_ip_host({"192.0.2.9": "", "x.example.test": " ".join(ips(2000) + ips(2000))})
    chains = parse(rendered)

    assert ip_host_exempt(chains, "192.0.2.9") and ip_host_exempt(chains, ips(2000)[-1])
    assert len(re.findall(r"10\\\.0\\\.0\\\.1[|)]", rendered)) == 1


def test_ip_host_past_the_bound_extra_literals_lose_the_exception_and_nothing_else_changes():
    literals = ips6(20000)  # about 45 bytes each: past 100 chunks of 8,177 bytes
    rendered = render_ip_host({"pad.example.test": " ".join(literals)})
    chains = parse(rendered)

    assert len([i for i in rule_ids(rendered) if 9800300 <= int(i) < 9800400]) == MAX_CHUNKS
    assert max(len(o.encode()) for o in operands(rendered)) <= HOST_CAP
    assert ip_host_exempt(chains, f"[{literals[0]}]") and not ip_host_exempt(chains, f"[{literals[-1]}]")
    assert not ip_host_exempt(chains, "10.0.0.5")


def test_ip_host_an_oversized_literal_is_skipped_and_the_others_keep_the_exception():
    huge = ":".join(["a"] * (HOST_CAP // 2 + 10))  # a bare "IPv6" name longer than a chunk
    chains = parse(render_ip_host({"pad.example.test": " ".join([huge, "10.0.0.5"] + ips(2000, 172))}))

    assert ip_host_exempt(chains, "10.0.0.5") and not ip_host_exempt(chains, f"[{huge}]")


# --- UTF-8: the budget counts bytes, not characters --------------------------------------------------------------------


def uni_names(count: int, prefix: str) -> list:
    """Names of 18 three-byte characters plus an ASCII tail: about 45 characters and 80 bytes each."""
    return [f"{'テスト' * 6}{prefix}{i:05d}.example.test" for i in range(count)]


@pytest.mark.parametrize("count", [150, 400, 2500])
def test_ui_utf8_names_are_budgeted_in_bytes(count):
    # 150 names: about 6,700 characters but 12,000 bytes, so a character count would keep the single regex.
    rendered = render_ui({"ui.example.test": ("yes", " ".join(["ui.example.test"] + uni_names(count, "u")))})
    chains = parse(rendered)
    hosts = uni_names(count, "u")

    assert "setvar" in rendered and max(len(o.encode()) for o in operands(rendered)) <= HOST_CAP
    assert all(ui_exempt(chains, h) for h in (hosts[0], hosts[count // 2], hosts[-1], "ui.example.test"))
    assert not ui_exempt(chains, "テスト.example.test")


@pytest.mark.parametrize("count", [150, 400, 2500])
def test_antibot_utf8_names_are_budgeted_in_bytes(count):
    rendered = render_antibot({"a.example.test": ("captcha", " ".join(["a.example.test"] + uni_names(count, "a")))})
    chains = parse(rendered)
    hosts = uni_names(count, "a")

    assert "setvar" in rendered and max(len(o.encode()) for o in operands(rendered)) <= HOST_CAP
    assert all(antibot_allowed(chains, h) for h in (hosts[0], hosts[count // 2], hosts[-1], "a.example.test"))
    assert not antibot_allowed(chains, "テスト.example.test")


def test_ui_and_antibot_a_name_longer_than_a_chunk_in_bytes_but_not_in_characters_is_skipped():
    huge = "あ" * (HOST_CAP // 3 + 100) + ".example.test"  # about 2,800 characters but 8,500 bytes
    ui = parse(render_ui({"ui.example.test": ("yes", " ".join([huge, "ui.example.test"] + uni_names(300, "u")))}))
    antibot = parse(render_antibot({"a.example.test": ("captcha", " ".join([huge, "a.example.test"] + uni_names(300, "a")))}))

    assert ui_exempt(ui, "ui.example.test") and not ui_exempt(ui, huge)
    assert antibot_allowed(antibot, "a.example.test") and not antibot_allowed(antibot, huge)
