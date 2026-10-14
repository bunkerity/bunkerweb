"""Execute identifier accessor expressions with jQuery's numeric coercion contract."""

import json
import re
import subprocess
from pathlib import Path

import pytest

PAGES = Path(__file__).resolve().parents[3] / "src/ui/app/static/js/pages"


@pytest.mark.parametrize(
    "page",
    ["configs", "jobs", "plugins-grid", "templates", "services", "bans", "instances", "service-resources", "config_edit", "template-settings-page", "reports"],
)
def test_identifier_accessors_keep_digit_only_ids_as_strings(page):
    source = (PAGES / f"{page}.js").read_text()
    keys = r"config-(?:name|service)|job|plugin|plugin-id|template-id|template-dom-id|templateId|template|service-id|resource-id|service|instance|report-id|hostname"
    accessors = re.findall(rf'\.(data|attr)\("((?:data-)?(?:{keys}))"\)', source)
    assert accessors, page
    script = """
const assert = require('node:assert/strict');
const row = {data: () => 0, attr: () => '0'};
for (const [method, key] of ACCESSORS) {
  assert.equal(row[method](key), '0', `${method}(${key}) coerces digit-only identifier`);
}
""".replace("ACCESSORS", json.dumps(accessors))
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
