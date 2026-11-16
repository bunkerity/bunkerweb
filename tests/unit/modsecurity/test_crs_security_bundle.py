"""Keep the stable CRS bundle's three 4.30.0 security fixes when vendoring."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3] / "src/common/core/modsecurity/files/coreruleset-v4/rules"


def test_charset_header_name_is_case_insensitive():
    rules = (ROOT / "REQUEST-920-PROTOCOL-ENFORCEMENT.conf").read_text()
    actions = rules.split('"id:920480,', 1)[1].split("msg:", 1)[0]
    assert "t:lowercase" in actions


def test_multipart_checks_every_charset_value():
    rules = (ROOT / "REQUEST-922-MULTIPART-ATTACK.conf").read_text()
    assert "setvar:'tx.multipart_headers_charset_counter=0'" in rules
    assert "setvar:'tx.922100_charset_%{tx.multipart_headers_charset_counter}" in rules
    assert "SecRule TX:/^922100_charset_/" in rules


def test_command_injection_rules_inspect_request_path():
    rules = (ROOT / "REQUEST-932-APPLICATION-ATTACK-RCE.conf").read_text()
    targets = dict((rule_id, target) for target, rule_id in re.findall(r'^SecRule (\S+).*\n\s+"id:(932\d+),', rules, re.M))
    assert "REQUEST_FILENAME" in targets["932230"].split("|")
