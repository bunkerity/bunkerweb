"""Sort field blocks without sorting their configured values or changing file bytes."""

import pytest
from _lua_request_helpers import ROOT, requires_lua, run
from _lua_state_helpers import run_lua

pytestmark = requires_lua


@pytest.mark.parametrize("canonical", ['{ "https://z.example/c", "https://a.example/c" }', "{}", "nil"])
def test_template_orders_fields_and_preserves_value_order(canonical):
    rendered = run_lua(f"""
local template = dofile("{ROOT}/src/deps/src/lua-resty-template/lib/resty/template.lua")
io.write(template.process_file("{ROOT}/src/common/core/securitytxt/files/security.txt", {{
    acknowledgements = {{ "https://z.example/thanks", "https://a.example/thanks" }},
    canonical = {canonical},
    contact = {{ "mailto:z@example.com", "mailto:a@example.com" }},
    csaf = {{ "https://z.example/csaf", "https://a.example/csaf" }},
    encryption = {{ "https://z.example/key", "https://a.example/key" }},
    expires = "2030-01-02T03:04:05Z",
    hiring = {{ "https://z.example/jobs", "https://a.example/jobs" }},
    policy = {{ "https://z.example/policy", "https://a.example/policy" }},
    preferred_lang = "fr, en", server_name = "www.example.com", uri = "/.well-known/security.txt"
}}))
""")
    canonical_lines = (
        "Canonical: https://z.example/c\nCanonical: https://a.example/c\n"
        if canonical.startswith("{ ")
        else "Canonical: https://www.example.com/.well-known/security.txt\n"
    )
    assert rendered == (
        "Acknowledgments: https://z.example/thanks\n"
        "Acknowledgments: https://a.example/thanks\n" + canonical_lines + "Contact: mailto:z@example.com\n"
        "Contact: mailto:a@example.com\n"
        "CSAF: https://z.example/csaf\n"
        "CSAF: https://a.example/csaf\n"
        "Encryption: https://z.example/key\n"
        "Encryption: https://a.example/key\n"
        "Expires: 2030-01-02T03:04:05Z\n"
        "Hiring: https://z.example/jobs\n"
        "Hiring: https://a.example/jobs\n"
        "Policy: https://z.example/policy\n"
        "Policy: https://a.example/policy\n"
        "Preferred-Languages: fr, en\n"
    )


def test_init_preserves_numeric_configuration_order_for_repeatable_fields():
    out = run(
        "securitytxt",
        """
MULTI_VARS = { global = {} }
for _, field in ipairs({ "CONTACT", "ACKNOWLEDGEMENTS", "CANONICAL", "CSAF", "ENCRYPTION", "HIRING", "POLICY" }) do
    MULTI_VARS.global["SECURITYTXT_" .. field .. "_10"] = "tenth"
    MULTI_VARS.global["SECURITYTXT_" .. field] = "first"
    MULTI_VARS.global["SECURITYTXT_" .. field .. "_2"] = "second"
end
local result = PLUGIN:new(ctx()):init()
emit("ok", result.ret)
for field, values in pairs(STORE.plugin_securitytxt_security_policies.global) do
    if type(values) == "table" then emit(field, table.concat(values, ",")) end
end
""",
    )
    assert out.pop("ok") == "true"
    assert out == dict.fromkeys(("contact", "acknowledgements", "canonical", "csaf", "encryption", "hiring", "policy"), "first,second,tenth")
