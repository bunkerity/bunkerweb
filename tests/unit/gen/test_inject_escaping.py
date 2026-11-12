from pathlib import Path

import jinja2
import pytest

TEMPLATE = Path(__file__).resolve().parents[3] / "src/common/core/inject/confs/server-http/inject.conf"


@pytest.mark.parametrize("setting,tag", [("INJECT_HEAD", "head"), ("INJECT_BODY", "body")])
@pytest.mark.parametrize(
    "value,escaped",
    [
        ("<script>f('x');</script>", r"<script>f(\'x\');</script>"),
        (r'<script>const p="C:\tmp\new";</script>', r'<script>const p="C:\\tmp\\new";</script>'),
        (r"<span>backslash \' quote</span>", r"<span>backslash \\\' quote</span>"),
        ("<script>f();g();</script>", "<script>f();g();</script>"),
        ('<span>double "quotes"</span>', '<span>double "quotes"</span>'),
    ],
)
def test_inject_escapes_nginx_single_quoted_values(setting, tag, value, escaped):
    variables = {"INJECT_HEAD": "", "INJECT_BODY": "", setting: value}
    rendered = jinja2.Environment().from_string(TEMPLATE.read_text()).render(**variables)
    assert rendered.strip() == f"sub_filter '</{tag}>' '{escaped}</{tag}>';"
